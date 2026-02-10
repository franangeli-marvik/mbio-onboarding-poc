import base64
import json
import logging
import os
import shutil
import time
import asyncio
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, WorkerOptions, cli, llm
from livekit.agents.metrics import UsageCollector
from livekit.plugins.openai import realtime as openai_realtime
from livekit.plugins.google import realtime as google_realtime

from agent.prompts import AGENT_INSTRUCTION, EXTRACTION_PROMPT
from core.config import MODEL_PROVIDER, GCP_PROJECT, GCP_LOCATION, DATA_DIR
from core.clients import get_openai_client

load_dotenv()

logging.getLogger("opentelemetry.exporter.otlp.proto.http._log_exporter").setLevel(
    logging.CRITICAL
)
logging.getLogger("opentelemetry.exporter.otlp.proto.http.trace_exporter").setLevel(
    logging.CRITICAL
)


def setup_langfuse():
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3333")
    if not public_key or not secret_key:
        print("[AGENT] Langfuse keys not set, skipping tracing setup")
        return
    try:
        from livekit.agents.telemetry import set_tracer_provider
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host.rstrip('/')}/api/public/otel"
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth}"
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        set_tracer_provider(provider)
        print(f"[AGENT] Langfuse tracing enabled -> {host}")
    except Exception as e:
        print(f"[AGENT] Failed to setup Langfuse tracing: {e}")

OUTPUT_DIR = Path(DATA_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_realtime_model():
    if MODEL_PROVIDER == "gemini":
        return google_realtime.RealtimeModel(
            model="gemini-live-2.5-flash-native-audio",
            voice="Puck",
            temperature=0.8,
            vertexai=True,
            project=GCP_PROJECT,
            location=GCP_LOCATION,
        )
    return openai_realtime.RealtimeModel(
        model="gpt-4o-realtime-preview",
        voice="alloy",
        modalities=["audio", "text"],
    )


def format_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


PHASE_KEYWORDS = {
    "school": [
        "education", "school", "university", "college", "degree",
        "major", "study", "studying", "academic", "student",
    ],
    "life": [
        "achievement", "accomplishment", "proud", "interests", "hobby",
        "hobbies", "outside work", "free time", "experience",
    ],
    "skills": [
        "skills", "technical", "abilities", "expertise", "proficient",
        "programming", "tools", "capabilities",
    ],
    "impact": [
        "impact", "legacy", "change", "contribute", "future",
        "goals", "aspiration", "make a difference", "world",
    ],
}


def detect_phase_from_text(text: str) -> str:
    text_lower = text.lower()
    for phase in ["impact", "skills", "life", "school"]:
        for keyword in PHASE_KEYWORDS[phase]:
            if keyword in text_lower:
                return phase
    return "school"


async def send_to_frontend(room, data: dict):
    try:
        if room and hasattr(room, "local_participant") and room.local_participant:
            payload = json.dumps(data).encode("utf-8")
            await room.local_participant.publish_data(payload, reliable=True)
    except Exception:
        pass


def find_and_copy_audio(session, ctx, audio_output_path: Path) -> bool:
    possible_paths: list[Path] = []

    if hasattr(session, "_recorder_io") and session._recorder_io:
        recorder = session._recorder_io
        if hasattr(recorder, "output_path") and recorder.output_path:
            possible_paths.append(Path(recorder.output_path))

    if hasattr(ctx, "session_directory"):
        possible_paths.append(ctx.session_directory / "audio.ogg")

    console_recordings = Path("console-recordings")
    if console_recordings.exists():
        session_dirs = sorted(console_recordings.glob("session-*"), reverse=True)
        for session_dir in session_dirs[:3]:
            possible_paths.append(session_dir / "audio.ogg")

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

    transcript_text = "\n".join(
        f"{item['role'].upper()}: {item['text']}" for item in transcript
    )

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": transcript_text},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {}


def build_agent_instructions(briefing: dict | None) -> str:
    if not briefing:
        return AGENT_INSTRUCTION

    candidate_context = briefing.get("candidate_context", "")
    guidelines = briefing.get("conversation_guidelines", "")
    if isinstance(guidelines, dict):
        guidelines = "\n".join(f"- {k}: {v}" for k, v in guidelines.items())
    questions_script = briefing.get("questions_script", [])
    topics_to_avoid = briefing.get("topics_to_avoid", [])
    personalization_hints = briefing.get("personalization_hints", [])

    questions_block = ""
    for i, q in enumerate(questions_script, 1):
        question = q.get("question", "") if isinstance(q, dict) else str(q)
        notes = q.get("notes", "") if isinstance(q, dict) else ""
        questions_block += f"\n{i}. {question}"
        if notes:
            questions_block += f"\n   (Note: {notes})"

    avoid_block = ""
    if topics_to_avoid:
        avoid_block = "\n- ".join(topics_to_avoid)

    hints_block = ""
    if personalization_hints:
        hints_block = "\n- ".join(personalization_hints)

    total_questions = len(questions_script)

    return f"""# Role & Objective
You are a professional interviewer helping candidates enhance their resume.
Your goal is to cover exactly {total_questions} interview questions, gather detailed answers, and then end the session.

# Personality & Tone
## Tone
- Warm, encouraging, and conversational
- Concise — keep responses to 2-3 sentences per turn
- Use the candidate's name occasionally to make it personal

## Language
- The conversation will be ONLY in English.
- Do NOT respond in any other language even if the user speaks Spanish, Italian, French, or any other language.
- If the user speaks another language, acknowledge in English and continue in English.

# Context
## Candidate Background
{candidate_context}

## Conversation Guidelines
{guidelines}

# Instructions
- Ask ONE question at a time, then wait for the candidate's response
- Acknowledge what they share before moving to the next topic
- If they share something interesting, ask ONE brief follow-up
- Do NOT repeat questions already answered
{f"- TOPICS TO AVOID: {avoid_block}" if avoid_block else ""}
{f"- PERSONALIZATION HINTS: {hints_block}" if hints_block else ""}

# Conversation Flow
## Questions ({total_questions} total) — ask IN ORDER:
{questions_block}

## Completion
- After ALL {total_questions} questions are covered, thank the candidate warmly
- Tell them their enhanced resume will be ready shortly
- Say a brief goodbye in English
- IMMEDIATELY call end_interview() — do NOT wait for the candidate to respond

## Early Exit
- If the candidate says goodbye in ANY language (bye, chau, adios, ciao, see you, etc.) or wants to leave:
  1. Say a brief warm farewell in English
  2. IMMEDIATELY call end_interview()
- Do NOT continue asking questions after the candidate wants to leave

# Tools
- end_interview(): Call this IMMEDIATELY after your farewell message. Do NOT skip this function call. This is CRITICAL.
- Before calling end_interview(), always say a short farewell like "Thank you for your time. Your enhanced resume will be ready shortly!"
"""


class Assistant(Agent):
    def __init__(self, instructions: str | None = None) -> None:
        super().__init__(instructions=instructions or AGENT_INSTRUCTION)

    @llm.function_tool
    async def end_interview(self):
        """End the interview session. Call this after your farewell message."""
        await self.session.drain()
        await self.session.aclose()


INACTIVITY_TIMEOUT = 300


async def entrypoint(ctx: agents.JobContext):
    setup_langfuse()
    await ctx.connect()

    room_name = ctx.room.name
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"{room_name}_{session_timestamp}"
    session_dir = OUTPUT_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    audio_output_path = session_dir / "audio.ogg"
    json_path = session_dir / "session.json"

    session_start_time = time.time()
    usage_collector = UsageCollector()
    transcript_history: list[dict] = []
    session_closed = False

    model = get_realtime_model()
    session = AgentSession(llm=model)

    last_user_speech_end: list[float | None] = [None]
    last_activity_time = [time.time()]
    latency_measurements: list[float] = []
    current_phase = ["school"]

    async def check_inactivity():
        while not session_closed:
            await asyncio.sleep(30)
            if session_closed:
                break
            elapsed = time.time() - last_activity_time[0]
            if elapsed > INACTIVITY_TIMEOUT:
                await session.drain()
                await session.aclose()
                break

    asyncio.create_task(check_inactivity())

    @session.on("user_input_transcribed")
    def on_user_input(event):
        last_user_speech_end[0] = time.time()
        last_activity_time[0] = time.time()
        transcript_history.append(
            {
                "role": "user",
                "text": event.transcript,
                "timestamp": last_user_speech_end[0],
                "is_final": event.is_final,
            }
        )
        asyncio.create_task(
            send_to_frontend(
                ctx.room,
                {
                    "type": "transcript",
                    "role": "user",
                    "text": event.transcript,
                    "is_final": event.is_final,
                    "timestamp": time.time(),
                },
            )
        )

    async def process_user_note(note_text: str):
        try:
            transcript_history.append(
                {
                    "role": "user",
                    "text": f"[Written note] {note_text}",
                    "timestamp": time.time(),
                }
            )
            await session.generate_reply(
                instructions=f"The user just typed this note: '{note_text}'. Acknowledge it briefly and incorporate this information. If it's a URL or link, confirm you've noted it."
            )
        except Exception:
            pass

    @session.on("agent_started_speaking")
    def on_agent_started(event):
        last_activity_time[0] = time.time()
        if last_user_speech_end[0] is not None:
            latency = time.time() - last_user_speech_end[0]
            latency_measurements.append(latency)

    @session.on("agent_speech_committed")
    def on_agent_speech(event):
        if hasattr(event, "content") and event.content:
            detected_phase = detect_phase_from_text(event.content)
            if detected_phase != current_phase[0]:
                current_phase[0] = detected_phase

            transcript_history.append(
                {"role": "agent", "text": event.content, "timestamp": time.time()}
            )
            asyncio.create_task(
                send_to_frontend(
                    ctx.room,
                    {
                        "type": "transcript",
                        "role": "agent",
                        "text": event.content,
                        "is_final": True,
                        "phase": current_phase[0],
                        "timestamp": time.time(),
                    },
                )
            )

    @session.on("metrics_collected")
    def on_metrics(event):
        usage_collector.collect(event.metrics)

    @session.on("close")
    def on_close(event):
        nonlocal session_closed
        session_closed = True
        session_end_time = time.time()
        duration_seconds = session_end_time - session_start_time

        usage = usage_collector.get_summary()
        audio_saved = find_and_copy_audio(session, ctx, audio_output_path)
        extracted_profile = extract_profile(transcript_history)

        latency_stats = {}
        if latency_measurements:
            latency_stats = {
                "avg_ms": round(
                    sum(latency_measurements) / len(latency_measurements) * 1000, 0
                ),
                "min_ms": round(min(latency_measurements) * 1000, 0),
                "max_ms": round(max(latency_measurements) * 1000, 0),
                "measurements": len(latency_measurements),
            }

        metadata = {
            "session_id": session_id,
            "room_name": room_name,
            "timestamp": datetime.now().isoformat(),
            "model_provider": MODEL_PROVIDER,
            "close_reason": event.reason.value if event.reason else "unknown",
            "duration": {
                "seconds": round(duration_seconds, 2),
                "formatted": format_duration(duration_seconds),
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
                "cached_tokens": usage.llm_prompt_cached_tokens,
            },
            "audio_file": "audio.ogg" if audio_saved else None,
            "transcript": transcript_history,
            "extracted_profile": extracted_profile,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        os._exit(0)

    briefing = None
    print(f"[AGENT] Room metadata raw: {ctx.room.metadata[:500] if ctx.room.metadata else 'EMPTY'}")
    try:
        if ctx.room.metadata:
            room_meta = json.loads(ctx.room.metadata)
            briefing = room_meta.get("interview_briefing")
            print(f"[AGENT] Briefing found: {briefing is not None}, questions: {len(briefing.get('questions_script', [])) if briefing else 0}")
        else:
            print("[AGENT] WARNING: No room metadata available")
    except Exception as e:
        print(f"[AGENT] ERROR parsing metadata: {e}")

    agent_instructions = build_agent_instructions(briefing)
    assistant = Assistant(instructions=agent_instructions)

    await session.start(room=ctx.room, agent=assistant, record=True)

    def on_data_received(data_packet: rtc.DataPacket):
        try:
            message = json.loads(data_packet.data.decode("utf-8"))
            if message.get("type") == "user_note":
                note_text = message.get("text", "")
                asyncio.create_task(process_user_note(note_text))
        except Exception:
            pass

    ctx.room.on("data_received", on_data_received)

    user_name = "there"
    for participant in ctx.room.remote_participants.values():
        if participant.name:
            user_name = participant.name.split()[0]
            break

    if user_name == "there":
        await asyncio.sleep(2)
        for participant in ctx.room.remote_participants.values():
            if participant.name:
                user_name = participant.name.split()[0]
                break

    first_question = ""
    if briefing and briefing.get("questions_script"):
        q = briefing["questions_script"][0]
        first_question = q.get("question", "") if isinstance(q, dict) else str(q)

    if first_question:
        personalized_instruction = (
            f"IMPORTANT: Speak ONLY in English. "
            f"The user's name is {user_name}. Greet them warmly by name in English and "
            f"start with this first question: {first_question}. "
            f"Keep your greeting brief. Do NOT use any other language."
        )
    else:
        personalized_instruction = (
            f"IMPORTANT: Speak ONLY in English. "
            f"The user's name is {user_name}. Greet them warmly by name in English and "
            f"start the interview. Ask about their primary career goal. "
            f"Keep your greeting brief. Do NOT use any other language."
        )

    await session.generate_reply(instructions=personalized_instruction)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
