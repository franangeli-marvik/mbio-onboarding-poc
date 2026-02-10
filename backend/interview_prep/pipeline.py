import time
from typing import Optional

from langgraph.graph import StateGraph, END

from interview_prep.schemas import InterviewPrepState
from interview_prep.agents import (
    profile_analyzer_node,
    question_planner_node,
    interview_briefer_node,
)


def should_continue_to_planner(state: InterviewPrepState) -> str:
    if state.get("profile_analysis"):
        return "continue"
    return "end_with_error"


def should_continue_to_briefer(state: InterviewPrepState) -> str:
    if state.get("interview_plan"):
        return "continue"
    return "end_with_error"


def error_handler_node(state: InterviewPrepState) -> dict:
    return {
        "interview_briefing": {
            "candidate_context": f"Interview with {state.get('user_name', 'candidate')}. Some preparation steps failed.",
            "conversation_guidelines": "Conduct a standard interview. Ask about their background, goals, and experiences.",
            "questions_script": [
                {"question": "Can you tell me about yourself and your background?", "notes": "Standard opener"},
                {"question": "What are your main career goals?", "notes": "Understand direction"},
                {"question": "What achievement are you most proud of?", "notes": "Explore highlights"},
                {"question": "What impact do you want to make?", "notes": "Closing question"},
            ],
            "topics_to_avoid": [],
            "personalization_hints": ["Use their name", "Be encouraging"],
        }
    }


def build_interview_prep_graph() -> StateGraph:
    workflow = StateGraph(InterviewPrepState)

    workflow.add_node("profile_analyzer", profile_analyzer_node)
    workflow.add_node("question_planner", question_planner_node)
    workflow.add_node("interview_briefer", interview_briefer_node)
    workflow.add_node("error_handler", error_handler_node)

    workflow.set_entry_point("profile_analyzer")

    workflow.add_conditional_edges(
        "profile_analyzer",
        should_continue_to_planner,
        {"continue": "question_planner", "end_with_error": "error_handler"},
    )
    workflow.add_conditional_edges(
        "question_planner",
        should_continue_to_briefer,
        {"continue": "interview_briefer", "end_with_error": "error_handler"},
    )

    workflow.add_edge("interview_briefer", END)
    workflow.add_edge("error_handler", END)

    return workflow


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_interview_prep_graph()
        _compiled_graph = workflow.compile()
    return _compiled_graph


graph = get_compiled_graph()


async def run_interview_prep_pipeline(
    resume_data: dict,
    life_stage: str,
    user_name: str,
    tenant_id: str | None = None,
    position_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    from observability.tracing import PipelineTrace
    from tenants.loader import load_tenant, resolve_position

    tenant_config = None
    if tenant_id:
        tenant = load_tenant(tenant_id)
        tenant_config = resolve_position(tenant, position_id)

    with PipelineTrace(
        pipeline_name="interview_prep",
        user_name=user_name,
        life_stage=life_stage,
        session_id=session_id,
        metadata={
            "resume_sections": list(resume_data.keys()),
            "tenant_id": tenant_id,
        },
    ) as trace:
        initial_state: InterviewPrepState = {
            "resume_data": resume_data,
            "life_stage": life_stage,
            "user_name": user_name,
            "tenant_config": tenant_config,
            "profile_analysis": None,
            "interview_plan": None,
            "interview_briefing": None,
            "errors": [],
        }

        compiled = get_compiled_graph()

        start_total = time.time()
        import asyncio
        final_state = await asyncio.to_thread(compiled.invoke, initial_state)
        total_duration = (time.time() - start_total) * 1000

        if final_state.get("profile_analysis"):
            pa = final_state["profile_analysis"]
            trace.log_node(
                "profile_analyzer",
                input_data={"resume_keys": list(resume_data.keys())},
                output_data={
                    "strengths": len(pa.get("strengths", [])),
                    "gaps": len(pa.get("gaps", [])),
                    "hooks": len(pa.get("interesting_hooks", [])),
                },
                duration_ms=total_duration / 3,
            )

        if final_state.get("interview_plan"):
            ip = final_state["interview_plan"]
            trace.log_node(
                "question_planner",
                input_data={"has_profile_analysis": True},
                output_data={
                    "phases": len(ip.get("phases", [])),
                    "total_questions": sum(
                        len(p.get("questions", [])) for p in ip.get("phases", [])
                    ),
                },
                duration_ms=total_duration / 3,
            )

        if final_state.get("interview_briefing"):
            ib = final_state["interview_briefing"]
            trace.log_node(
                "interview_briefer",
                input_data={"has_interview_plan": True},
                output_data={
                    "questions": len(ib.get("questions_script", [])),
                    "hints": len(ib.get("personalization_hints", [])),
                },
                duration_ms=total_duration / 3,
            )

        trace_id = trace.session_id

    return {
        "interview_briefing": final_state.get("interview_briefing"),
        "profile_analysis": final_state.get("profile_analysis"),
        "interview_plan": final_state.get("interview_plan"),
        "errors": final_state.get("errors", []),
        "trace_id": trace_id,
    }
