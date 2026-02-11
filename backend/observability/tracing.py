from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Any

from core.clients import get_langfuse_client


class _NullGeneration:
    def update(self, **kwargs):
        pass


@contextmanager
def traced_generation(name: str, *, model: str, prompt=None, input_data=None):
    langfuse = get_langfuse_client()
    if not langfuse:
        yield _NullGeneration()
        return

    try:
        with langfuse.start_as_current_observation(
            as_type="generation",
            name=name,
            model=model,
            prompt=prompt,
            input=_safe_serialize(input_data),
        ) as gen:
            yield gen
    except Exception:
        yield _NullGeneration()


class PipelineTrace:
    def __init__(
        self,
        pipeline_name: str,
        user_name: str = "unknown",
        life_stage: str = "unknown",
        session_id: str | None = None,
        metadata: dict | None = None,
    ):
        self.pipeline_name = pipeline_name
        self.user_name = user_name
        self.life_stage = life_stage
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.metadata = metadata or {}
        self.start_time: datetime | None = None
        self.langfuse = get_langfuse_client()
        self._span = None
        self.nodes_logged: list[dict] = []

    def __enter__(self):
        self.start_time = datetime.now()

        if self.langfuse:
            try:
                self._span = self.langfuse.start_as_current_span(name=self.pipeline_name)
                self._span.__enter__()
                self.langfuse.update_current_trace(
                    user_id=self.user_name,
                    session_id=self.session_id,
                    metadata={
                        "life_stage": self.life_stage,
                        "started_at": self.start_time.isoformat(),
                        **self.metadata,
                    },
                )
            except Exception:
                self._span = None

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._span:
            try:
                self.langfuse.update_current_span(
                    output={
                        "status": "ERROR" if exc_type else "OK",
                        "nodes_completed": len(self.nodes_logged),
                        "nodes": self.nodes_logged,
                    },
                )
                self._span.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass

        if self.langfuse:
            try:
                self.langfuse.flush()
            except Exception:
                pass

    def log_node(
        self,
        node_name: str,
        input_data: Any,
        output_data: Any,
        duration_ms: float,
        model: str = "gemini-2.0-flash",
        error: str | None = None,
    ):
        self.nodes_logged.append(
            {"node": node_name, "duration_ms": round(duration_ms, 1), "success": error is None}
        )

        if not self.langfuse:
            return

        try:
            with self.langfuse.start_as_current_observation(
                as_type="generation",
                name=node_name,
                model=model,
                input=_safe_serialize(input_data),
            ):
                self.langfuse.update_current_generation(
                    output=_safe_serialize(output_data),
                    metadata={"duration_ms": round(duration_ms, 1)},
                )
        except Exception:
            pass


def traced_node(node_name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(state, *args, **kwargs):
            start_time = datetime.now()
            error = None
            result = None

            try:
                result = func(state, *args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                trace = state.get("_trace") if isinstance(state, dict) else None
                if trace and isinstance(trace, PipelineTrace):
                    trace.log_node(
                        node_name=node_name,
                        input_data=_extract_input_summary(state),
                        output_data=_extract_output_summary(result),
                        duration_ms=duration_ms,
                        error=error,
                    )

        return wrapper
    return decorator


def _safe_serialize(data: Any) -> Any:
    if data is None:
        return None
    try:
        if hasattr(data, "model_dump"):
            return data.model_dump()
        if hasattr(data, "dict"):
            return data.dict()
        if isinstance(data, (dict, list, str, int, float, bool)):
            return data
        return str(data)[:500]
    except Exception:
        return str(data)[:500]


def _extract_input_summary(state: dict) -> dict:
    if not isinstance(state, dict):
        return {"type": str(type(state))}
    return {
        "user_name": state.get("user_name"),
        "life_stage": state.get("life_stage"),
        "has_resume": bool(state.get("resume_data")),
        "has_profile_analysis": bool(state.get("profile_analysis")),
        "has_interview_plan": bool(state.get("interview_plan")),
    }


def _extract_output_summary(result: Any) -> dict:
    if result is None:
        return {"type": "None"}
    if not isinstance(result, dict):
        return {"type": str(type(result))}

    summary = {}

    if "profile_analysis" in result:
        pa = result["profile_analysis"]
        if isinstance(pa, dict):
            summary["profile_analysis"] = {
                "strengths_count": len(pa.get("strengths", [])),
                "gaps_count": len(pa.get("gaps", [])),
                "hooks_count": len(pa.get("interesting_hooks", [])),
            }

    if "interview_plan" in result:
        ip = result["interview_plan"]
        if isinstance(ip, dict):
            phases = ip.get("phases", [])
            summary["interview_plan"] = {
                "phases_count": len(phases),
                "questions_count": sum(len(p.get("questions", [])) for p in phases),
            }

    if "interview_briefing" in result:
        ib = result["interview_briefing"]
        if isinstance(ib, dict):
            summary["interview_briefing"] = {
                "questions_count": len(ib.get("questions_script", [])),
                "hints_count": len(ib.get("personalization_hints", [])),
            }

    if "errors" in result:
        summary["errors"] = result["errors"]

    return summary
