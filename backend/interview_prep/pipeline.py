"""
Interview Prep Pipeline

LangGraph pipeline that orchestrates the three agents to prepare
personalized voice interviews.

Flow: resume_data -> Profile Analyzer -> Question Planner -> Interview Briefer -> briefing

Following LangGraph 2026 best practices:
- Simple linear graph with direct edges
- Each node is a pure function returning partial state
- Error handling at node level
"""

from typing import Optional
from langgraph.graph import StateGraph, START, END

from .schemas import InterviewPrepState
from .agents import (
    profile_analyzer_node,
    question_planner_node,
    interview_briefer_node,
)


def should_continue_to_planner(state: InterviewPrepState) -> str:
    """
    Router: Check if profile analysis succeeded before continuing.
    """
    if state.get("profile_analysis"):
        return "continue"
    else:
        return "end_with_error"


def should_continue_to_briefer(state: InterviewPrepState) -> str:
    """
    Router: Check if question planning succeeded before continuing.
    """
    if state.get("interview_plan"):
        return "continue"
    else:
        return "end_with_error"


def error_handler_node(state: InterviewPrepState) -> dict:
    """
    Node that handles errors and provides fallback response.
    """
    print("---ERROR HANDLER: Pipeline encountered errors---")
    errors = state.get("errors", [])
    print(f"---Errors: {errors}---")
    
    # Return a minimal fallback briefing
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
            "personalization_hints": ["Use their name", "Be encouraging"]
        }
    }


def build_interview_prep_graph() -> StateGraph:
    """
    Build the LangGraph pipeline for interview preparation.
    
    Graph structure:
    START -> profile_analyzer -> question_planner -> interview_briefer -> END
                  |                    |
                  v                    v
              (if error)          (if error)
                  |                    |
                  +-----> error_handler -----> END
    """
    # Create the graph with our state type
    workflow = StateGraph(InterviewPrepState)
    
    # Add nodes
    workflow.add_node("profile_analyzer", profile_analyzer_node)
    workflow.add_node("question_planner", question_planner_node)
    workflow.add_node("interview_briefer", interview_briefer_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # Set entry point
    workflow.set_entry_point("profile_analyzer")
    
    # Add conditional edge after profile analyzer
    workflow.add_conditional_edges(
        "profile_analyzer",
        should_continue_to_planner,
        {
            "continue": "question_planner",
            "end_with_error": "error_handler"
        }
    )
    
    # Add conditional edge after question planner
    workflow.add_conditional_edges(
        "question_planner",
        should_continue_to_briefer,
        {
            "continue": "interview_briefer",
            "end_with_error": "error_handler"
        }
    )
    
    # Final edges to END
    workflow.add_edge("interview_briefer", END)
    workflow.add_edge("error_handler", END)
    
    return workflow


# Compile the graph once at module load
_compiled_graph = None


def get_compiled_graph():
    """Get or create the compiled graph (singleton pattern)."""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_interview_prep_graph()
        _compiled_graph = workflow.compile()
    return _compiled_graph


# Export compiled graph for LangGraph Studio
# This is what langgraph.json points to
graph = get_compiled_graph()


async def run_interview_prep_pipeline(
    resume_data: dict,
    life_stage: str,
    user_name: str,
    session_id: Optional[str] = None,
) -> dict:
    """
    Run the interview preparation pipeline.
    
    Args:
        resume_data: Parsed resume JSON from resume_parser
        life_stage: "student" or "professional"
        user_name: Candidate's name for personalization
        session_id: Optional session ID for tracing
        
    Returns:
        dict with:
        - interview_briefing: Ready-to-use context for voice agent
        - profile_analysis: Analysis results (for debugging)
        - interview_plan: Question plan (for debugging)
        - errors: Any errors encountered
        - trace_id: Langfuse trace ID (if configured)
    """
    from .observability import PipelineTrace
    
    print(f"\n{'='*60}")
    print(f"INTERVIEW PREP PIPELINE: Starting for {user_name}")
    print(f"Life Stage: {life_stage}")
    print(f"{'='*60}\n")
    
    # Use Langfuse tracing
    with PipelineTrace(
        pipeline_name="interview_prep",
        user_name=user_name,
        life_stage=life_stage,
        session_id=session_id,
        metadata={
            "resume_sections": list(resume_data.keys()),
            "has_work": bool(resume_data.get("work")),
            "has_education": bool(resume_data.get("education")),
            "has_skills": bool(resume_data.get("skills")),
        }
    ) as trace:
        
        # Initialize state
        initial_state: InterviewPrepState = {
            "resume_data": resume_data,
            "life_stage": life_stage,
            "user_name": user_name,
            "profile_analysis": None,
            "interview_plan": None,
            "interview_briefing": None,
            "errors": [],
        }
        
        # Get compiled graph
        graph = get_compiled_graph()
        
        # Run the pipeline with step-by-step logging
        import time
        
        # Execute and track each step
        start_total = time.time()
        final_state = graph.invoke(initial_state)
        total_duration = (time.time() - start_total) * 1000
        
        # Log summary to trace
        if final_state.get("profile_analysis"):
            pa = final_state["profile_analysis"]
            trace.log_node(
                "profile_analyzer",
                input_data={"resume_keys": list(resume_data.keys())},
                output_data={
                    "strengths": len(pa.get("strengths", [])),
                    "gaps": len(pa.get("gaps", [])),
                    "hooks": len(pa.get("interesting_hooks", []))
                },
                duration_ms=total_duration / 3  # Approximate
            )
        
        if final_state.get("interview_plan"):
            ip = final_state["interview_plan"]
            trace.log_node(
                "question_planner",
                input_data={"has_profile_analysis": True},
                output_data={
                    "phases": len(ip.get("phases", [])),
                    "total_questions": sum(len(p.get("questions", [])) for p in ip.get("phases", []))
                },
                duration_ms=total_duration / 3
            )
        
        if final_state.get("interview_briefing"):
            ib = final_state["interview_briefing"]
            trace.log_node(
                "interview_briefer",
                input_data={"has_interview_plan": True},
                output_data={
                    "questions": len(ib.get("questions_script", [])),
                    "hints": len(ib.get("personalization_hints", []))
                },
                duration_ms=total_duration / 3
            )
        
        trace_id = trace.session_id
    
    print(f"\n{'='*60}")
    print(f"INTERVIEW PREP PIPELINE: Completed")
    print(f"Errors: {final_state.get('errors', [])}")
    print(f"Trace ID: {trace_id}")
    print(f"{'='*60}\n")
    
    return {
        "interview_briefing": final_state.get("interview_briefing"),
        "profile_analysis": final_state.get("profile_analysis"),
        "interview_plan": final_state.get("interview_plan"),
        "errors": final_state.get("errors", []),
        "trace_id": trace_id,
    }


# For debugging: allow running the pipeline directly
if __name__ == "__main__":
    import asyncio
    import json
    
    # Sample resume data for testing
    test_resume = {
        "basics": {
            "name": "Francesco Angeli",
            "email": "francesco@example.com",
            "summary": "Software engineer with 5 years of experience",
            "location": {"city": "San Francisco", "country": "USA"}
        },
        "work": [
            {
                "company": "Tech Corp",
                "position": "Senior Software Engineer",
                "startDate": "2022-01",
                "highlights": ["Led team of 4", "Built microservices architecture"]
            }
        ],
        "education": [
            {
                "institution": "UC Berkeley",
                "area": "Computer Science",
                "studyType": "Bachelor"
            }
        ],
        "skills": [
            {"category": "Languages", "keywords": ["Python", "TypeScript", "Go"]},
            {"category": "Frameworks", "keywords": ["FastAPI", "React", "Next.js"]}
        ]
    }
    
    async def main():
        result = await run_interview_prep_pipeline(
            resume_data=test_resume,
            life_stage="professional",
            user_name="Francesco"
        )
        print("\n" + "="*60)
        print("FINAL RESULT:")
        print("="*60)
        print(json.dumps(result, indent=2))
    
    asyncio.run(main())
