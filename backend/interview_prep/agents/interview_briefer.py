import json
from typing import Any

from core.clients import get_gemini_client
from agent.prompt_manager import get_langfuse_prompt
from observability.tracing import traced_generation
from interview_prep.schemas import InterviewPrepState, InterviewBriefing
from interview_prep.prompts import get_interview_briefer_system, get_interview_briefer_user

MODEL = "gemini-2.0-flash"


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
            if tc.get("key_areas"):
                tenant_block += f"\nKey areas to explore: {', '.join(tc['key_areas'])}"
            if tc.get("must_verify"):
                tenant_block += f"\nMust verify: {', '.join(tc['must_verify'])}"

        user_prompt = get_interview_briefer_user(
            user_name=state["user_name"],
            life_stage=state["life_stage"],
            profile_analysis_json=profile_analysis_json,
            interview_plan_json=interview_plan_json,
        ) + tenant_block

        system_prompt = get_interview_briefer_system()
        contents = [
            {"role": "user", "parts": [{"text": system_prompt}]},
            {"role": "model", "parts": [{"text": "I understand. I will create a comprehensive briefing document for the voice agent."}]},
            {"role": "user", "parts": [{"text": user_prompt}]},
        ]

        lf_prompt = get_langfuse_prompt("pipeline/interview-briefer-system")

        with traced_generation(
            "interview_briefer",
            model=MODEL,
            prompt=lf_prompt,
            input_data={"system": system_prompt, "user": user_prompt[:2000]},
        ) as gen:
            client = get_gemini_client()
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config={"temperature": 0.4, "response_mime_type": "application/json"},
            )

            usage = getattr(response, "usage_metadata", None)
            gen.update(
                output=response.text,
                usage_details={
                    "input": getattr(usage, "prompt_token_count", 0),
                    "output": getattr(usage, "candidates_token_count", 0),
                } if usage else None,
            )

        briefing = InterviewBriefing(**json.loads(response.text))
        return {"interview_briefing": briefing.model_dump()}

    except json.JSONDecodeError as e:
        return {"errors": state.get("errors", []) + [f"Interview briefer JSON error: {e}"]}
    except Exception as e:
        return {"errors": state.get("errors", []) + [f"Interview briefer error: {e}"]}
