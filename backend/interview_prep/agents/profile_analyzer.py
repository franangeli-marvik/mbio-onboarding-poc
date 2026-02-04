"""
Agent 1: Profile Analyzer

Analyzes parsed resume data to identify strengths, gaps, and interesting
topics to explore in the voice interview.
"""

import json
from typing import Any
from ..schemas import InterviewPrepState, ProfileAnalysis
from ..prompts import PROFILE_ANALYZER_SYSTEM, PROFILE_ANALYZER_USER


def get_llm():
    """Get the LLM client for this agent."""
    from google import genai
    from google.genai import types
    import os
    
    # Try environment variable first (local dev)
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key:
        return genai.Client(api_key=api_key)
    else:
        # Use Application Default Credentials (GCP)
        return genai.Client()


def profile_analyzer_node(state: InterviewPrepState) -> dict[str, Any]:
    """
    LangGraph node that analyzes the candidate's profile.
    
    Input: resume_data, life_stage, user_name
    Output: profile_analysis dict
    
    Following LangGraph best practices:
    - Pure function that returns partial state updates
    - No mutation of input state
    - Returns dict with only changed fields
    """
    print("---PROFILE ANALYZER: Starting analysis---")
    
    try:
        # Prepare the prompt with resume context
        resume_json = json.dumps(state["resume_data"], indent=2, ensure_ascii=False)
        
        user_prompt = PROFILE_ANALYZER_USER.format(
            user_name=state["user_name"],
            life_stage=state["life_stage"],
            resume_json=resume_json
        )
        
        # Call Gemini
        client = get_llm()
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"role": "user", "parts": [{"text": PROFILE_ANALYZER_SYSTEM}]},
                {"role": "model", "parts": [{"text": "I understand. I will analyze the resume and provide structured insights for the voice interview."}]},
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            config={
                "temperature": 0.3,  # Low temperature for consistent analysis
                "response_mime_type": "application/json",
            }
        )
        
        # Parse the response
        analysis_dict = json.loads(response.text)
        
        # Validate with Pydantic (optional but recommended)
        analysis = ProfileAnalysis(**analysis_dict)
        
        print(f"---PROFILE ANALYZER: Completed. Found {len(analysis.strengths)} strengths, {len(analysis.gaps)} gaps---")
        
        return {
            "profile_analysis": analysis.model_dump(),
            "life_stage": analysis.life_stage  # Update if corrected by analysis
        }
        
    except json.JSONDecodeError as e:
        print(f"---PROFILE ANALYZER: JSON parsing error: {e}---")
        return {
            "errors": state.get("errors", []) + [f"Profile analyzer JSON error: {str(e)}"]
        }
    except Exception as e:
        print(f"---PROFILE ANALYZER: Error: {e}---")
        return {
            "errors": state.get("errors", []) + [f"Profile analyzer error: {str(e)}"]
        }
