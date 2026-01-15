import json
import logging
import os
import shutil
import time
import asyncio
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, WorkerOptions, cli, llm
from livekit.agents.metrics import UsageCollector

# Importar plugins en el thread principal (requerido por LiveKit)
from livekit.plugins.openai import realtime as openai_realtime
from livekit.plugins.google import realtime as google_realtime

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION, EXTRACTION_PROMPT

load_dotenv()

# Silenciar errores de OpenTelemetry
logging.getLogger("opentelemetry.exporter.otlp.proto.http._log_exporter").setLevel(logging.CRITICAL)
logging.getLogger("opentelemetry.exporter.otlp.proto.http.trace_exporter").setLevel(logging.CRITICAL)

# Carpeta de salida
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Cliente OpenAI para extractor post-conversación
openai_client = OpenAI()

# Configuración del modelo: "openai" o "gemini"
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai").lower()


def get_realtime_model():
    """
    Retorna el modelo realtime según la configuración.
    Soporta OpenAI y Gemini (via Vertex AI).
    Docs: https://docs.livekit.io/agents/models/realtime/plugins/gemini/
    """
    if MODEL_PROVIDER == "gemini":
        # Usar Vertex AI con Service Account
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "mbio-profile-creation")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        print(f"[INFO] Project: {project_id}, Location: {location}")
        
        return google_realtime.RealtimeModel(
            model="gemini-live-2.5-flash-native-audio",
            voice="Puck",
            temperature=0.8,
            vertexai=True,
            project=project_id,
            location=location,
        )
    else:
        print(f"[INFO] Usando modelo: OpenAI Realtime")
        return openai_realtime.RealtimeModel(
            model="gpt-4o-realtime-preview",
            voice="alloy",
            modalities=["audio", "text"],
        )


def format_duration(seconds: float) -> str:
    """Formatea la duración en formato HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# Phase detection keywords
PHASE_KEYWORDS = {
    'school': ['education', 'school', 'university', 'college', 'degree', 'major', 'study', 'studying', 'academic', 'student'],
    'life': ['achievement', 'accomplishment', 'proud', 'interests', 'hobby', 'hobbies', 'outside work', 'free time', 'experience'],
    'skills': ['skills', 'technical', 'abilities', 'expertise', 'proficient', 'programming', 'tools', 'capabilities'],
    'impact': ['impact', 'legacy', 'change', 'contribute', 'future', 'goals', 'aspiration', 'make a difference', 'world']
}

def detect_phase_from_text(text: str) -> str:
    """Detect interview phase from agent's text."""
    text_lower = text.lower()
    
    # Check phases in reverse order (later phases take priority)
    for phase in ['impact', 'skills', 'life', 'school']:
        for keyword in PHASE_KEYWORDS[phase]:
            if keyword in text_lower:
                return phase
    return 'school'  # Default to school


async def send_to_frontend(room, data: dict):
    """Send data to frontend via data channel."""
    try:
        if room and hasattr(room, 'local_participant') and room.local_participant:
            payload = json.dumps(data).encode('utf-8')
            await room.local_participant.publish_data(payload, reliable=True)
            print(f"[DEBUG] Sent to frontend: {data.get('type')} - {data.get('role')}")
        else:
            print(f"[DEBUG] Room not ready, skipping send: {data.get('type')}")
    except Exception as e:
        print(f"[WARN] Failed to send data to frontend: {e}")


def find_and_copy_audio(session, ctx, audio_output_path: Path) -> bool:
    """Busca y copia el archivo de audio grabado."""
    possible_paths = []
    
    if hasattr(session, '_recorder_io') and session._recorder_io:
        recorder = session._recorder_io
        if hasattr(recorder, 'output_path') and recorder.output_path:
            possible_paths.append(Path(recorder.output_path))
    
    if hasattr(ctx, 'session_directory'):
        possible_paths.append(ctx.session_directory / "audio.ogg")
    
    console_recordings = Path("console-recordings")
    if console_recordings.exists():
        session_dirs = sorted(console_recordings.glob("session-*"), reverse=True)
        for session_dir in session_dirs[:3]:
            audio_path = session_dir / "audio.ogg"
            possible_paths.append(audio_path)
    
    for source_path in possible_paths:
        if source_path.exists():
            try:
                shutil.copy2(source_path, audio_output_path)
                return True
            except Exception:
                pass
    
    return False


def extract_profile(transcript: list) -> dict:

    if not transcript:
        return {}
    
    transcript_text = "\n".join([
        f"{item['role'].upper()}: {item['text']}" 
        for item in transcript
    ])
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": transcript_text}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[WARN] Error en extracción: {e}")
        return {}


class Assistant(Agent):
    def __init__(self, end_conversation_callback) -> None:
        super().__init__(instructions=AGENT_INSTRUCTION)
        self._end_conversation_callback = end_conversation_callback
    
    @llm.function_tool
    async def end_interview(self) -> str:
        """
        Call this function when the user indicates they want to end the conversation.
        This includes any form of goodbye, farewell, or indication that they need to leave.
        Examples: "bye", "goodbye", "see you", "I have to go", "that's all", "thanks, bye", 
        "chau", "adiós", "nos vemos", "me tengo que ir", "hasta luego", etc.
        
        IMPORTANT: Call this function AFTER you say your final goodbye to the user.
        """
        print("\n[INFO] El agente detectó fin de conversación")
        self._end_conversation_callback()
        return "Interview ended successfully. Goodbye!"


async def entrypoint(ctx: agents.JobContext):
    print(f"[INFO] Entrypoint started, connecting to room...")
    await ctx.connect()
    print(f"[INFO] Connected to room: {ctx.room.name}")
    
    room_name = ctx.room.name
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"{room_name}_{session_timestamp}"
    
    audio_output_path = OUTPUT_DIR / f"{session_id}.ogg"
    json_path = OUTPUT_DIR / f"{session_id}.json"
    
    session_start_time = time.time()
    usage_collector = UsageCollector()
    transcript_history = []
    shutdown_initiated = False

    model = get_realtime_model()
    
    session = AgentSession(
        llm=model,
    )
    
    def end_conversation():
        nonlocal shutdown_initiated
        if not shutdown_initiated:
            shutdown_initiated = True
            print("[INFO] Ending conversation...")
            session.shutdown(drain=True)
    
    last_user_speech_end = [None] 
    last_activity_time = [time.time()]  # Track last activity for timeout
    latency_measurements = []
    
    current_phase = ['school']  # Track current phase
    
    # Inactivity timeout (5 minutes)
    INACTIVITY_TIMEOUT = 300  # seconds
    
    async def check_inactivity():
        """Check for inactivity and close session if timeout exceeded"""
        while not shutdown_initiated:
            await asyncio.sleep(30)  # Check every 30 seconds
            if shutdown_initiated:
                break
            elapsed = time.time() - last_activity_time[0]
            if elapsed > INACTIVITY_TIMEOUT:
                print(f"[INFO] Session inactive for {elapsed:.0f}s, closing...")
                end_conversation()
                break
    
    # Start inactivity checker
    asyncio.create_task(check_inactivity())
    
    @session.on("user_input_transcribed")
    def on_user_input(event):
        last_user_speech_end[0] = time.time()
        last_activity_time[0] = time.time()  # Update activity timestamp
        transcript_history.append({
            "role": "user",
            "text": event.transcript,
            "timestamp": last_user_speech_end[0],
            "is_final": event.is_final
        })
        
        # Send transcript to frontend
        asyncio.create_task(send_to_frontend(ctx.room, {
            "type": "transcript",
            "role": "user",
            "text": event.transcript,
            "is_final": event.is_final,
            "timestamp": time.time()
        }))
    
    # Handle text notes from the user (sent via data channel)
    async def process_user_note(note_text: str):
        """Process user note asynchronously"""
        try:
            print(f"[INFO] Processing note: {note_text}")
            # Add to transcript
            transcript_history.append({
                "role": "user",
                "text": f"[Written note] {note_text}",
                "timestamp": time.time()
            })
            
            # Send the note to the agent so it can acknowledge/respond
            await session.generate_reply(
                instructions=f"The user just typed this note: '{note_text}'. Acknowledge it briefly and incorporate this information. If it's a URL or link, confirm you've noted it."
            )
        except Exception as e:
            print(f"[WARN] Error processing note: {e}")
    
    @session.on("agent_started_speaking")
    def on_agent_started(event):
        last_activity_time[0] = time.time()  # Update activity timestamp
        if last_user_speech_end[0] is not None:
            latency = time.time() - last_user_speech_end[0]
            latency_measurements.append(latency)
            print(f"[LATENCY] Respuesta en {latency*1000:.0f}ms")
    
    @session.on("agent_speech_committed")
    def on_agent_speech(event):
        if hasattr(event, 'content') and event.content:
            # Detect phase from agent's speech
            detected_phase = detect_phase_from_text(event.content)
            if detected_phase != current_phase[0]:
                current_phase[0] = detected_phase
                print(f"[INFO] Phase changed to: {detected_phase}")
            
            transcript_history.append({
                "role": "agent",
                "text": event.content,
                "timestamp": time.time()
            })
            
            # Send transcript and phase to frontend
            asyncio.create_task(send_to_frontend(ctx.room, {
                "type": "transcript",
                "role": "agent",
                "text": event.content,
                "is_final": True,
                "phase": current_phase[0],
                "timestamp": time.time()
            }))
    
    @session.on("metrics_collected")
    def on_metrics(event):
        usage_collector.collect(event.metrics)
    
    @session.on("close")
    def on_close(event):
        session_end_time = time.time()
        duration_seconds = session_end_time - session_start_time
        
        usage = usage_collector.get_summary()
        audio_saved = find_and_copy_audio(session, ctx, audio_output_path)
        
        print("[INFO] Extrayendo perfil del transcript...")
        extracted_profile = extract_profile(transcript_history)
        
        # Calcular métricas de latencia
        latency_stats = {}
        if latency_measurements:
            latency_stats = {
                "avg_ms": round(sum(latency_measurements) / len(latency_measurements) * 1000, 0),
                "min_ms": round(min(latency_measurements) * 1000, 0),
                "max_ms": round(max(latency_measurements) * 1000, 0),
                "measurements": len(latency_measurements),
                "all_ms": [round(l * 1000, 0) for l in latency_measurements]
            }
        
        metadata = {
            "session_id": session_id,
            "room_name": room_name,
            "timestamp": datetime.now().isoformat(),
            "model_provider": MODEL_PROVIDER,
            "close_reason": event.reason.value if event.reason else "unknown",
            "duration": {
                "seconds": round(duration_seconds, 2),
                "formatted": format_duration(duration_seconds)
            },
            "latency": latency_stats,
            "token_usage": {
                "input_tokens": usage.llm_input_tokens,
                "output_tokens": usage.llm_output_tokens,
                "total_tokens": usage.llm_input_tokens + usage.llm_output_tokens,
                "audio_input_tokens": usage.llm_input_audio_tokens,
                "audio_output_tokens": usage.llm_output_audio_tokens,
                "text_input_tokens": usage.llm_input_text_tokens,
                "text_output_tokens": usage.llm_output_text_tokens,
                "cached_tokens": usage.llm_prompt_cached_tokens
            },
            "audio_file": str(audio_output_path.name) if audio_saved else None,
            "transcript": transcript_history,
            "extracted_profile": extracted_profile
        }
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*50}")
        print(f"[INFO] Sesión finalizada: {session_id}")
        print(f"[INFO] Modelo: {MODEL_PROVIDER}")
        print(f"[INFO] Duración: {format_duration(duration_seconds)}")
        if latency_stats:
            print(f"[INFO] Latencia promedio: {latency_stats['avg_ms']}ms (min: {latency_stats['min_ms']}ms, max: {latency_stats['max_ms']}ms)")
        print(f"[INFO] Tokens totales: {metadata['token_usage']['total_tokens']}")
        print(f"[INFO] Mensajes en transcript: {len(transcript_history)}")
        if audio_saved:
            print(f"[INFO] Audio: {audio_output_path}")
        print(f"[INFO] Metadata: {json_path}")
        print(f"{'='*50}\n")
        
        os._exit(0)

    assistant = Assistant(end_conversation_callback=end_conversation)

    await session.start(
        room=ctx.room,
        agent=assistant,
        record=True,
    )
    
    print("[INFO] Session started, registering data channel handler...")
    
    # Register data channel handler using rtc.RoomEvent
    def on_data_received(data_packet: rtc.DataPacket):
        try:
            message = json.loads(data_packet.data.decode('utf-8'))
            if message.get('type') == 'user_note':
                note_text = message.get('text', '')
                print(f"[INFO] Received note from user: {note_text}")
                asyncio.create_task(process_user_note(note_text))
        except Exception as e:
            print(f"[WARN] Error processing data: {e}")
    
    ctx.room.on("data_received", on_data_received)

    # Wait for user to connect and get their name
    user_name = "there"  # default
    for participant in ctx.room.remote_participants.values():
        if participant.name:
            user_name = participant.name.split()[0]  # Use first name
            break
    
    # If no user yet, wait a bit for them to join
    if user_name == "there":
        await asyncio.sleep(2)
        for participant in ctx.room.remote_participants.values():
            if participant.name:
                user_name = participant.name.split()[0]
                break
    
    print(f"[INFO] Starting interview with: {user_name}")
    
    # Personalized session instruction
    personalized_instruction = f"""
    The user's name is {user_name}. Greet them warmly by name and start the interview.
    Ask about their primary career goal or what they're working toward right now.
    Keep your greeting brief - just a warm hello and dive into the first question.
    """

    await session.generate_reply(
        instructions=personalized_instruction
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
