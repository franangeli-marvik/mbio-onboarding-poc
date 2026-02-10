import json
from typing import Any

from core.clients import get_gemini_client
from interview_prep.schemas import InterviewPrepState, InterviewBriefing
from interview_prep.prompts import INTERVIEW_BRIEFER_SYSTEM, INTERVIEW_BRIEFER_USER


def interview_briefer_node(state: InterviewPrepState) -> dict[str, Any]:
    if not state.get("profile_analysis") or not state.get("interview_plan"):
        return {
            "errors": state.get("errors", [])
            + ["Interview briefer: Missing profile analysis or interview plan"]
        }

    try:
        profile_analysis_json = json.dumps(state["profile_analysis"], indent=2, ensure_ascii=False)
        interview_plan_json = json.dumps(state["interview_plan"], indent=2, ensure_ascii=False)

        tenant_block = ""
        if state.get("tenant_config"):
            tc = state["tenant_config"]
            tenant_block = f"\n\n## Recruiter Tone & Style\nTone: {tc.get('tone', 'supportive')}\nFocus: {tc.get('focus_area', 'General')}"
            if tc.get("custom_instructions"):
                tenant_block += f"\nCustom instructions: {tc['custom_instructions']}"

        user_prompt = INTERVIEW_BRIEFER_USER.format(
            user_name=state["user_name"],
            life_stage=state["life_stage"],
            profile_analysis_json=profile_analysis_json,
            interview_plan_json=interview_plan_json,
        ) + tenant_block

        client = get_gemini_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"role": "user", "parts": [{"text": INTERVIEW_BRIEFER_SYSTEM}]},
                {"role": "model", "parts": [{"text": "I understand. I will create a comprehensive briefing document for the voice agent."}]},
                {"role": "user", "parts": [{"text": user_prompt}]},
            ],
            config={"temperature": 0.4, "response_mime_type": "application/json"},
        )

        briefing = InterviewBriefing(**json.loads(response.text))
        return {"interview_briefing": briefing.model_dump()}

    except json.JSONDecodeError as e:
        return {"errors": state.get("errors", []) + [f"Interview briefer JSON error: {e}"]}
    except Exception as e:
        return {"errors": state.get("errors", []) + [f"Interview briefer error: {e}"]}
