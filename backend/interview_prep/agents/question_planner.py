import json
from typing import Any

from core.clients import get_gemini_client
from agent.prompt_manager import get_langfuse_prompt
from observability.tracing import traced_generation
from interview_prep.schemas import InterviewPrepState, InterviewPlan
from interview_prep.prompts import QUESTION_PLANNER_SYSTEM, get_question_planner_user

MODEL = "gemini-2.0-flash"


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

        contents = [
            {"role": "user", "parts": [{"text": QUESTION_PLANNER_SYSTEM}]},
            {"role": "model", "parts": [{"text": "I understand. I will create a personalized interview plan with questions tailored to this candidate."}]},
            {"role": "user", "parts": [{"text": user_prompt}]},
        ]

        lf_prompt = get_langfuse_prompt("pipeline/question-planner-system")

        with traced_generation(
            "question_planner",
            model=MODEL,
            prompt=lf_prompt,
            input_data={"system": QUESTION_PLANNER_SYSTEM, "user": user_prompt[:2000]},
        ) as gen:
            client = get_gemini_client()
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config={"temperature": 0.5, "response_mime_type": "application/json"},
            )

            usage = getattr(response, "usage_metadata", None)
            gen.update(
                output=response.text,
                usage_details={
                    "input": getattr(usage, "prompt_token_count", 0),
                    "output": getattr(usage, "candidates_token_count", 0),
                } if usage else None,
            )

        plan = InterviewPlan(**json.loads(response.text))
        return {"interview_plan": plan.model_dump()}

    except json.JSONDecodeError as e:
        return {"errors": state.get("errors", []) + [f"Question planner JSON error: {e}"]}
    except Exception as e:
        return {"errors": state.get("errors", []) + [f"Question planner error: {e}"]}
