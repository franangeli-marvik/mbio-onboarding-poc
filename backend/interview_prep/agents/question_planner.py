import json
from typing import Any

from core.clients import get_gemini_client
from interview_prep.schemas import InterviewPrepState, InterviewPlan
from interview_prep.prompts import QUESTION_PLANNER_SYSTEM, get_question_planner_user


def question_planner_node(state: InterviewPrepState) -> dict[str, Any]:
    if not state.get("profile_analysis"):
        return {"errors": state.get("errors", []) + ["Question planner: Missing profile analysis"]}

    try:
        profile_analysis_json = json.dumps(state["profile_analysis"], indent=2, ensure_ascii=False)

        tenant_block = ""
        if state.get("tenant_config"):
            tc = state["tenant_config"]
            tenant_block = f"\n\n## Recruiter Requirements\nFocus area: {tc.get('focus_area', 'General')}\nTone: {tc.get('tone', 'supportive')}"
            if tc.get("custom_instructions"):
                tenant_block += f"\nSpecial instructions: {tc['custom_instructions']}"

        user_prompt = get_question_planner_user(
            profile_analysis_json=profile_analysis_json,
            user_name=state["user_name"],
            life_stage=state["life_stage"],
        ) + tenant_block

        client = get_gemini_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"role": "user", "parts": [{"text": QUESTION_PLANNER_SYSTEM}]},
                {"role": "model", "parts": [{"text": "I understand. I will create a personalized interview plan with questions tailored to this candidate."}]},
                {"role": "user", "parts": [{"text": user_prompt}]},
            ],
            config={"temperature": 0.5, "response_mime_type": "application/json"},
        )

        plan = InterviewPlan(**json.loads(response.text))
        return {"interview_plan": plan.model_dump()}

    except json.JSONDecodeError as e:
        return {"errors": state.get("errors", []) + [f"Question planner JSON error: {e}"]}
    except Exception as e:
        return {"errors": state.get("errors", []) + [f"Question planner error: {e}"]}
