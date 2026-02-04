"""
Agent 3: Interview Briefer

Generates the final interview briefing that will be used as context
for the voice agent to conduct a personalized interview.
"""

import json
from typing import Any
from ..schemas import InterviewPrepState, InterviewBriefing
from ..prompts import INTERVIEW_BRIEFER_SYSTEM, INTERVIEW_BRIEFER_USER


def get_llm():
    """Get the LLM client for this agent."""
    from google import genai
    import os
    
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key:
        return genai.Client(api_key=api_key)
    else:
        return genai.Client()


def interview_briefer_node(state: InterviewPrepState) -> dict[str, Any]:
    """
    LangGraph node that generates the final interview briefing.
    
    Input: profile_analysis, interview_plan, life_stage, user_name
    Output: interview_briefing dict (ready for voice agent)
    
    Following LangGraph best practices:
    - Pure function that returns partial state updates
    - Final node in the pipeline
    """
    print("---INTERVIEW BRIEFER: Generating briefing---")
    
    # Check for required inputs
    if not state.get("profile_analysis") or not state.get("interview_plan"):
        print("---INTERVIEW BRIEFER: Missing required inputs, skipping---")
        return {
            "errors": state.get("errors", []) + ["Interview briefer: Missing profile analysis or interview plan"]
        }
    
    try:
        # Prepare the prompt
        profile_analysis_json = json.dumps(state["profile_analysis"], indent=2, ensure_ascii=False)
        interview_plan_json = json.dumps(state["interview_plan"], indent=2, ensure_ascii=False)
        
        user_prompt = INTERVIEW_BRIEFER_USER.format(
            user_name=state["user_name"],
            life_stage=state["life_stage"],
            profile_analysis_json=profile_analysis_json,
            interview_plan_json=interview_plan_json
        )
        
        # Call Gemini
        client = get_llm()
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"role": "user", "parts": [{"text": INTERVIEW_BRIEFER_SYSTEM}]},
                {"role": "model", "parts": [{"text": "I understand. I will create a comprehensive briefing document for the voice agent."}]},
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            config={
                "temperature": 0.4,
                "response_mime_type": "application/json",
            }
        )
        
        # Parse the response
        briefing_dict = json.loads(response.text)
        
        # Validate with Pydantic
        briefing = InterviewBriefing(**briefing_dict)
        
        print(f"---INTERVIEW BRIEFER: Generated briefing with {len(briefing.questions_script)} questions---")
        
        return {
            "interview_briefing": briefing.model_dump()
        }
        
    except json.JSONDecodeError as e:
        print(f"---INTERVIEW BRIEFER: JSON parsing error: {e}---")
        return {
            "errors": state.get("errors", []) + [f"Interview briefer JSON error: {str(e)}"]
        }
    except Exception as e:
        print(f"---INTERVIEW BRIEFER: Error: {e}---")
        return {
            "errors": state.get("errors", []) + [f"Interview briefer error: {str(e)}"]
        }
