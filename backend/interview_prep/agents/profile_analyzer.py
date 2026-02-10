import json
from typing import Any

from core.clients import get_gemini_client
from interview_prep.schemas import InterviewPrepState, ProfileAnalysis
from interview_prep.prompts import PROFILE_ANALYZER_SYSTEM, PROFILE_ANALYZER_USER


def profile_analyzer_node(state: InterviewPrepState) -> dict[str, Any]:
    try:
        resume_json = json.dumps(state["resume_data"], indent=2, ensure_ascii=False)

        tenant_block = ""
        if state.get("tenant_config"):
            tc = state["tenant_config"]
            tenant_block = f"\n\n## Recruiter Focus\nFocus area: {tc.get('focus_area', 'General')}\nTone: {tc.get('tone', 'supportive')}"
            if tc.get("custom_instructions"):
                tenant_block += f"\nSpecial instructions: {tc['custom_instructions']}"

        user_prompt = PROFILE_ANALYZER_USER.format(
            user_name=state["user_name"],
            life_stage=state["life_stage"],
            resume_json=resume_json,
        ) + tenant_block

        client = get_gemini_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"role": "user", "parts": [{"text": PROFILE_ANALYZER_SYSTEM}]},
                {"role": "model", "parts": [{"text": "I understand. I will analyze the resume and provide structured insights for the voice interview."}]},
                {"role": "user", "parts": [{"text": user_prompt}]},
            ],
            config={"temperature": 0.3, "response_mime_type": "application/json"},
        )

        analysis = ProfileAnalysis(**json.loads(response.text))

        return {
            "profile_analysis": analysis.model_dump(),
            "life_stage": analysis.life_stage,
        }

    except json.JSONDecodeError as e:
        return {"errors": state.get("errors", []) + [f"Profile analyzer JSON error: {e}"]}
    except Exception as e:
        return {"errors": state.get("errors", []) + [f"Profile analyzer error: {e}"]}
