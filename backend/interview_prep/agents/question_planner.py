"""
Agent 2: Question Planner

Creates a personalized interview plan based on the profile analysis,
with questions tailored to the specific candidate.
"""

import json
from typing import Any
from ..schemas import InterviewPrepState, InterviewPlan
from ..prompts import QUESTION_PLANNER_SYSTEM, QUESTION_PLANNER_USER


def get_llm():
    """Get the LLM client for this agent."""
    from google import genai
    import os
    
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key:
        return genai.Client(api_key=api_key)
    else:
        return genai.Client()


def question_planner_node(state: InterviewPrepState) -> dict[str, Any]:
    """
    LangGraph node that creates a personalized interview plan.
    
    Input: profile_analysis, life_stage, user_name
    Output: interview_plan dict
    
    Following LangGraph best practices:
    - Pure function that returns partial state updates
    - Depends on previous node output (profile_analysis)
    """
    print("---QUESTION PLANNER: Creating interview plan---")
    
    # Check for required input from previous node
    if not state.get("profile_analysis"):
        print("---QUESTION PLANNER: Missing profile_analysis, skipping---")
        return {
            "errors": state.get("errors", []) + ["Question planner: Missing profile analysis"]
        }
    
    try:
        # Prepare the prompt
        profile_analysis_json = json.dumps(state["profile_analysis"], indent=2, ensure_ascii=False)
        
        user_prompt = QUESTION_PLANNER_USER.format(
            profile_analysis_json=profile_analysis_json,
            user_name=state["user_name"],
            life_stage=state["life_stage"]
        )
        
        # Call Gemini
        client = get_llm()
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"role": "user", "parts": [{"text": QUESTION_PLANNER_SYSTEM}]},
                {"role": "model", "parts": [{"text": "I understand. I will create a personalized interview plan with questions tailored to this candidate."}]},
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            config={
                "temperature": 0.5,  # Slightly higher for creative questions
                "response_mime_type": "application/json",
            }
        )
        
        # Parse the response
        plan_dict = json.loads(response.text)
        
        # Validate with Pydantic
        plan = InterviewPlan(**plan_dict)
        
        total_questions = sum(len(phase.questions) for phase in plan.phases)
        print(f"---QUESTION PLANNER: Created {len(plan.phases)} phases with {total_questions} questions---")
        
        return {
            "interview_plan": plan.model_dump()
        }
        
    except json.JSONDecodeError as e:
        print(f"---QUESTION PLANNER: JSON parsing error: {e}---")
        return {
            "errors": state.get("errors", []) + [f"Question planner JSON error: {str(e)}"]
        }
    except Exception as e:
        print(f"---QUESTION PLANNER: Error: {e}---")
        return {
            "errors": state.get("errors", []) + [f"Question planner error: {str(e)}"]
        }
