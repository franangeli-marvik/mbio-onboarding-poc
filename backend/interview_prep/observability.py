"""
Observability Module for Interview Prep Pipeline

Integrates with Langfuse for self-hosted LLM observability.
Provides tracing, metrics, and debugging capabilities.

Langfuse V3 uses the @observe decorator pattern.
"""

import os
from typing import Optional, Any
from datetime import datetime
from functools import wraps
import json

# Langfuse client (lazy loaded)
_langfuse_client = None
_langfuse_configured = None


def get_langfuse():
    """Get or create Langfuse client."""
    global _langfuse_client, _langfuse_configured
    
    if _langfuse_configured is None:
        # Check if Langfuse is configured
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "http://localhost:3333")
        
        if public_key and secret_key:
            try:
                from langfuse import Langfuse
                _langfuse_client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host
                )
                _langfuse_configured = True
                print(f"[LANGFUSE] Connected to {host}")
            except Exception as e:
                print(f"[LANGFUSE] Failed to connect: {e}")
                _langfuse_client = None
                _langfuse_configured = False
        else:
            print("[LANGFUSE] Not configured (missing keys)")
            _langfuse_configured = False
    
    return _langfuse_client


def get_observe_decorator():
    """Get the @observe decorator from langfuse if available."""
    try:
        from langfuse.decorators import observe, langfuse_context
        return observe, langfuse_context
    except ImportError:
        return None, None


class PipelineTrace:
    """
    Context manager for tracing a complete pipeline execution.
    
    Usage:
        with PipelineTrace("interview_prep", user_name="Francesco") as trace:
            trace.log_node("profile_analyzer", input_data, output_data, duration_ms)
            ...
    """
    
    def __init__(
        self,
        pipeline_name: str,
        user_name: str = "unknown",
        life_stage: str = "unknown",
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        self.pipeline_name = pipeline_name
        self.user_name = user_name
        self.life_stage = life_stage
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.metadata = metadata or {}
        self.start_time = None
        self.langfuse = get_langfuse()
        self.trace = None
        self.nodes_logged = []
    
    def __enter__(self):
        self.start_time = datetime.now()
        
        if self.langfuse:
            try:
                # Langfuse V3 uses decorators, but we can still use low-level API
                from langfuse.decorators import langfuse_context
                
                # Update the context for this trace
                langfuse_context.update_current_trace(
                    name=self.pipeline_name,
                    session_id=self.session_id,
                    user_id=self.user_name,
                    metadata={
                        "life_stage": self.life_stage,
                        "started_at": self.start_time.isoformat(),
                        **self.metadata
                    }
                )
                self.trace = True  # Mark as active
                print(f"[LANGFUSE] Trace started: {self.session_id}")
            except Exception as e:
                # Fallback: just log locally
                print(f"[LANGFUSE] Using local logging (trace setup: {e})")
                self.trace = None
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now()
        duration_ms = (end_time - self.start_time).total_seconds() * 1000
        
        if self.trace:
            try:
                self.trace.update(
                    output={
                        "nodes_executed": len(self.nodes_logged),
                        "total_duration_ms": duration_ms,
                        "success": exc_type is None
                    }
                )
                # Flush to ensure data is sent
                self.langfuse.flush()
            except Exception as e:
                print(f"[LANGFUSE] Error finalizing trace: {e}")
        
        # Always log locally too
        print(f"[TRACE] Pipeline '{self.pipeline_name}' completed in {duration_ms:.0f}ms")
    
    def log_node(
        self,
        node_name: str,
        input_data: Any,
        output_data: Any,
        duration_ms: float,
        model: str = "gemini-2.0-flash",
        prompt: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log a single node execution."""
        
        self.nodes_logged.append({
            "node": node_name,
            "duration_ms": duration_ms,
            "success": error is None
        })
        
        if self.trace:
            try:
                # Create a generation span for LLM calls
                generation = self.trace.generation(
                    name=node_name,
                    model=model,
                    input=self._safe_serialize(input_data),
                    output=self._safe_serialize(output_data),
                    metadata={
                        "duration_ms": duration_ms,
                        "error": error
                    }
                )
                
                if prompt:
                    generation.update(input={"prompt": prompt[:1000]})  # Truncate long prompts
                
            except Exception as e:
                print(f"[LANGFUSE] Error logging node {node_name}: {e}")
        
        # Local log
        status = "✅" if error is None else "❌"
        print(f"[TRACE] {status} {node_name}: {duration_ms:.0f}ms")
    
    def _safe_serialize(self, data: Any) -> Any:
        """Safely serialize data for Langfuse."""
        if data is None:
            return None
        
        try:
            # Try to convert to dict if it's a Pydantic model
            if hasattr(data, 'model_dump'):
                return data.model_dump()
            elif hasattr(data, 'dict'):
                return data.dict()
            elif isinstance(data, (dict, list, str, int, float, bool)):
                return data
            else:
                return str(data)[:500]  # Truncate long strings
        except Exception:
            return str(data)[:500]


def traced_node(node_name: str):
    """
    Decorator to automatically trace a node function.
    
    Usage:
        @traced_node("profile_analyzer")
        def profile_analyzer_node(state):
            ...
    """
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
                
                # Get trace from state if available
                trace = state.get("_trace") if isinstance(state, dict) else None
                if trace and isinstance(trace, PipelineTrace):
                    trace.log_node(
                        node_name=node_name,
                        input_data=_extract_input_summary(state),
                        output_data=_extract_output_summary(result),
                        duration_ms=duration_ms,
                        error=error
                    )
        
        return wrapper
    return decorator


def _extract_input_summary(state: dict) -> dict:
    """Extract a summary of input state for logging."""
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
    """Extract a summary of output for logging."""
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
                "hooks_count": len(pa.get("interesting_hooks", []))
            }
    
    if "interview_plan" in result:
        ip = result["interview_plan"]
        if isinstance(ip, dict):
            phases = ip.get("phases", [])
            total_questions = sum(len(p.get("questions", [])) for p in phases)
            summary["interview_plan"] = {
                "phases_count": len(phases),
                "questions_count": total_questions
            }
    
    if "interview_briefing" in result:
        ib = result["interview_briefing"]
        if isinstance(ib, dict):
            summary["interview_briefing"] = {
                "questions_count": len(ib.get("questions_script", [])),
                "hints_count": len(ib.get("personalization_hints", []))
            }
    
    if "errors" in result:
        summary["errors"] = result["errors"]
    
    return summary
