"""
Multi-agent voice interview entrypoint.

Each interview phase (warmup, deep_dive, gaps, closing) is a separate LiveKit Agent
with a short, focused prompt. Agents hand off to each other via function tools.
This follows the LiveKit restaurant_agent.py pattern for reliable instruction following.
"""

import base64
import json
import logging
import os
import shutil
import time
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import WorkerOptions, cli
from livekit.agents.llm import function_tool
from livekit.agents.voice import Agent, AgentSession, RunContext
from livekit.agents.metrics import UsageCollector
from livekit.plugins.openai import realtime as openai_realtime
from livekit.plugins.google import realtime as google_realtime

from agent.prompts import AGENT_INSTRUCTION, EXTRACTION_PROMPT, build_phase_instructions
from core.config import MODEL_PROVIDER, GCP_PROJECT, GCP_LOCATION, DATA_DIR
from core.clients import get_openai_client

load_dotenv()

logging.getLogger("opentelemetry.exporter.otlp.proto.http._log_exporter").setLevel(
    logging.CRITICAL
)
logging.getLogger("opentelemetry.exporter.otlp.proto.http.trace_exporter").setLevel(
    logging.CRITICAL
)


# ---------------------------------------------------------------------------
# Langfuse OTEL tracing setup
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------
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
        model="gpt-realtime",
        voice="alloy",
        modalities=["audio", "text"],
    )


# ---------------------------------------------------------------------------
# Utilities (kept from original)
# ---------------------------------------------------------------------------
def format_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


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


# ---------------------------------------------------------------------------
# Shared interview state (passed via session.userdata)
# ---------------------------------------------------------------------------
@dataclass
class InterviewUserData:
    candidate_name: str = ""
    candidate_context: str = ""
    guidelines: str = ""
    topics_to_avoid: list[str] = field(default_factory=list)
    personalization_hints: list[str] = field(default_factory=list)
    phases: list[dict] = field(default_factory=list)
    current_phase_idx: int = 0
    transcript: list[dict] = field(default_factory=list)
    agents: dict[str, Agent] = field(default_factory=dict)
    prev_agent: Agent | None = None
    phase_names: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Base agent class (following LiveKit restaurant_agent pattern)
# ---------------------------------------------------------------------------
class BaseInterviewAgent(Agent):
    """Base class for all interview phase agents."""

    async def on_enter(self) -> None:
        """Called when this agent becomes active. Inherits conversation history."""
        agent_name = self.__class__.__name__
        print(f"[AGENT] Entering phase: {agent_name}")

        userdata: InterviewUserData = self.session.userdata
        chat_ctx = self.chat_ctx.copy()

        # Add previous agent's conversation history for context continuity
        if isinstance(userdata.prev_agent, Agent):
            truncated_chat_ctx = userdata.prev_agent.chat_ctx.copy(
                exclude_instructions=True,
                exclude_function_call=False,
                exclude_handoff=True,
                exclude_config_update=True,
            ).truncate(max_items=8)
            existing_ids = {item.id for item in chat_ctx.items}
            items_copy = [
                item for item in truncated_chat_ctx.items if item.id not in existing_ids
            ]
            chat_ctx.items.extend(items_copy)

        await self.update_chat_ctx(chat_ctx)

        # Generate a response: greeting for first agent, natural transition for subsequent
        if userdata.current_phase_idx == 0 and userdata.prev_agent is None:
            # First agent: warm greeting + first question from the instructions
            name = userdata.candidate_name or "there"
            self.session.generate_reply(
                instructions=(
                    f"Greet {name} warmly in English. "
                    f"Then ask your first question from the QUESTIONS TO ASK list. "
                    f"Keep it to 2 sentences."
                )
            )
        else:
            # Subsequent agents: natural transition, no tool call yet
            self.session.generate_reply(tool_choice="none")

    async def _transfer_to_next(self, context: RunContext) -> tuple[Agent, str]:
        """Transfer to the next phase agent."""
        userdata: InterviewUserData = context.userdata
        userdata.prev_agent = context.session.current_agent
        userdata.current_phase_idx += 1

        next_idx = userdata.current_phase_idx
        if next_idx < len(userdata.phase_names):
            next_name = userdata.phase_names[next_idx]
            next_agent = userdata.agents.get(next_name)
            if next_agent:
                print(f"[AGENT] Handoff: {self.__class__.__name__} -> {next_name}")
                return next_agent, f"Moving to {next_name} phase"

        # No more phases — end the interview
        print(f"[AGENT] No more phases, ending interview")
        await self.session.drain()
        await self.session.aclose()
        return self, "Interview complete"


# ---------------------------------------------------------------------------
# Phase agent factory
# ---------------------------------------------------------------------------
def create_phase_agent(
    phase_name: str,
    phase_goal: str,
    questions: list[dict],
    candidate_context: str,
    is_last_phase: bool,
    topics_to_avoid: list[str] | None = None,
    personalization_hints: list[str] | None = None,
) -> Agent:
    """Dynamically create a phase agent with the right instructions and tools."""
    instructions = build_phase_instructions(
        phase_name=phase_name,
        phase_goal=phase_goal,
        questions=questions,
        candidate_context=candidate_context,
        is_last_phase=is_last_phase,
        topics_to_avoid=topics_to_avoid,
        personalization_hints=personalization_hints,
    )

    print(f"[AGENT] Creating {phase_name} agent | questions={len(questions)} | "
          f"instructions_len={len(instructions)} | is_last={is_last_phase}")

    if is_last_phase:
        # Closing agent: has end_interview instead of move_to_next_phase
        class ClosingPhaseAgent(BaseInterviewAgent):
            def __init__(self):
                super().__init__(instructions=instructions)

            @function_tool()
            async def end_interview(self, context: RunContext):
                """End the interview session. Call this after your farewell message."""
                print(f"[AGENT] end_interview() called in closing phase")
                await self.session.drain()
                await self.session.aclose()

            @function_tool()
            async def early_exit(self, context: RunContext):
                """Use if the candidate wants to leave early."""
                print(f"[AGENT] early_exit() called")
                await self.session.drain()
                await self.session.aclose()

        return ClosingPhaseAgent()
    else:
        # Non-closing agent: has move_to_next_phase
        class InterviewPhaseAgent(BaseInterviewAgent):
            def __init__(self):
                super().__init__(instructions=instructions)

            @function_tool()
            async def move_to_next_phase(self, context: RunContext) -> tuple[Agent, str]:
                """Call when you've covered all questions in this phase."""
                print(f"[AGENT] move_to_next_phase() called from {phase_name}")
                return await self._transfer_to_next(context)

            @function_tool()
            async def end_interview(self, context: RunContext):
                """Use if the candidate wants to leave early."""
                print(f"[AGENT] end_interview() (early exit) from {phase_name}")
                await self.session.drain()
                await self.session.aclose()

        return InterviewPhaseAgent()


# ---------------------------------------------------------------------------
# Fallback: single agent when no pipeline plan is available
# ---------------------------------------------------------------------------
class FallbackAssistant(Agent):
    def __init__(self, instructions: str | None = None) -> None:
        super().__init__(instructions=instructions or AGENT_INSTRUCTION)

    async def on_enter(self) -> None:
        userdata: InterviewUserData = self.session.userdata
        name = userdata.candidate_name or "there"
        self.session.generate_reply(
            instructions=(
                f"Greet {name} warmly in English. "
                f"Then ask about their main career goal. "
                f"Keep it to 2 sentences."
            )
        )

    @function_tool()
    async def end_interview(self, context: RunContext):
        """End the interview session. Call this after your farewell message."""
        await self.session.drain()
        await self.session.aclose()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INACTIVITY_TIMEOUT = 300


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
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

    last_user_speech_end: list[float | None] = [None]
    last_activity_time = [time.time()]
    latency_measurements: list[float] = []

    # ------------------------------------------------------------------
    # Parse room metadata
    # ------------------------------------------------------------------
    briefing = None
    plan = None
    print(f"[AGENT] Room metadata raw: {ctx.room.metadata[:500] if ctx.room.metadata else 'EMPTY'}")
    try:
        if ctx.room.metadata:
            room_meta = json.loads(ctx.room.metadata)
            briefing = room_meta.get("interview_briefing")
            plan = room_meta.get("interview_plan")
            print(
                f"[AGENT] Briefing found: {briefing is not None}, "
                f"questions: {len(briefing.get('questions_script', [])) if briefing else 0}"
            )
            print(
                f"[AGENT] Plan found: {plan is not None}, "
                f"phases: {len(plan.get('phases', [])) if plan else 0}"
            )
        else:
            print("[AGENT] WARNING: No room metadata available")
    except Exception as e:
        print(f"[AGENT] ERROR parsing metadata: {e}")

    # ------------------------------------------------------------------
    # Resolve user name
    # ------------------------------------------------------------------
    user_name = "there"
    if briefing:
        # Try to get from metadata participant_name
        try:
            room_meta = json.loads(ctx.room.metadata)
            user_name = room_meta.get("participant_name", "there").split()[0]
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Build agents
    # ------------------------------------------------------------------
    use_multi_agent = plan is not None and len(plan.get("phases", [])) > 0
    model = get_realtime_model()

    if use_multi_agent:
        # ---- MULTI-AGENT PATH ----
        candidate_context = briefing.get("candidate_context", "") if briefing else ""
        topics_to_avoid = briefing.get("topics_to_avoid", []) if briefing else []
        personalization_hints = briefing.get("personalization_hints", []) if briefing else []

        phases = plan["phases"]
        phase_names = []
        agents_dict: dict[str, Agent] = {}

        for i, phase in enumerate(phases):
            phase_name = phase.get("phase_name", f"phase_{i}")
            phase_goal = phase.get("phase_goal", "")
            phase_questions = phase.get("questions", [])
            is_last = i == len(phases) - 1

            # Normalize phase name for dict key
            key = phase_name.lower().replace(" ", "_")
            phase_names.append(key)

            agent = create_phase_agent(
                phase_name=phase_name,
                phase_goal=phase_goal,
                questions=phase_questions,
                candidate_context=candidate_context,
                is_last_phase=is_last,
                topics_to_avoid=topics_to_avoid,
                personalization_hints=personalization_hints,
            )
            agents_dict[key] = agent

        userdata = InterviewUserData(
            candidate_name=user_name,
            candidate_context=candidate_context,
            topics_to_avoid=topics_to_avoid,
            personalization_hints=personalization_hints,
            phases=[p for p in phases],
            phase_names=phase_names,
            agents=agents_dict,
        )

        first_agent = agents_dict[phase_names[0]]
        print(
            f"[AGENT] Multi-agent mode: {len(phase_names)} phases "
            f"({', '.join(phase_names)}), starting with {phase_names[0]}"
        )

        session = AgentSession[InterviewUserData](
            llm=model,
            userdata=userdata,
        )
    else:
        # ---- FALLBACK: SINGLE AGENT ----
        print("[AGENT] Fallback mode: using single agent (no plan available)")
        first_agent = FallbackAssistant()
        userdata = InterviewUserData(candidate_name=user_name)
        session = AgentSession[InterviewUserData](
            llm=model,
            userdata=userdata,
        )

    # ------------------------------------------------------------------
    # Event handlers (shared for both paths)
    # ------------------------------------------------------------------
    async def check_inactivity():
        while not session_closed:
            await asyncio.sleep(30)
            if session_closed:
                break
            elapsed = time.time() - last_activity_time[0]
            if elapsed > INACTIVITY_TIMEOUT:
                print("[AGENT] Inactivity timeout reached, closing session")
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
                instructions=f"The user just typed this note: '{note_text}'. "
                "Acknowledge it briefly and incorporate this information. "
                "If it's a URL or link, confirm you've noted it."
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
            "multi_agent": use_multi_agent,
            "phases": [p.get("phase_name") for p in plan.get("phases", [])] if plan else [],
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

        print(
            f"[AGENT] Session closed | duration={duration_seconds:.1f}s | "
            f"transcript_turns={len(transcript_history)} | "
            f"reason={event.reason.value if event.reason else 'unknown'}"
        )

        # Safe shutdown: only hard-exit after a real session (>10s).
        # Very short sessions (<10s) are likely spurious close events;
        # killing the process would leave the Realtime model running
        # autonomously without Python control.
        if duration_seconds > 10:
            os._exit(0)
        else:
            print(
                f"[AGENT] Short session ({duration_seconds:.1f}s), "
                f"skipping os._exit to avoid orphaned model"
            )

    # ------------------------------------------------------------------
    # Start the session
    # ------------------------------------------------------------------
    await session.start(agent=first_agent, room=ctx.room, record=True)

    # Handle data channel messages (user notes)
    def on_data_received(data_packet: rtc.DataPacket):
        try:
            message = json.loads(data_packet.data.decode("utf-8"))
            if message.get("type") == "user_note":
                note_text = message.get("text", "")
                asyncio.create_task(process_user_note(note_text))
        except Exception:
            pass

    ctx.room.on("data_received", on_data_received)

    # ------------------------------------------------------------------
    # Resolve user name from participants (retry after 2s if needed)
    # ------------------------------------------------------------------
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

    # Update userdata with resolved name
    userdata.candidate_name = user_name

    # ------------------------------------------------------------------
    # Initial greeting is handled by on_enter() of the first agent.
    # No additional generate_reply here to avoid double-response.
    # ------------------------------------------------------------------
    print(f"[AGENT] Session started for {user_name}, on_enter handles greeting")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
