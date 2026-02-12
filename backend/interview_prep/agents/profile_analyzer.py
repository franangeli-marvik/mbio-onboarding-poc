import json
from typing import Any

from core.clients import get_gemini_client
from agent.prompt_manager import get_langfuse_prompt
from observability.tracing import traced_generation
from interview_prep.schemas import InterviewPrepState, ProfileAnalysis
from interview_prep.prompts import get_profile_analyzer_system, get_profile_analyzer_user

MODEL = "gemini-2.0-flash"


def profile_analyzer_node(state: InterviewPrepState) -> dict[str, Any]:
    try:
        resume_json = json.dumps(state["resume_data"], indent=2, ensure_ascii=False)

        tenant_block = ""
        if state.get("tenant_config"):
            tc = state["tenant_config"]
            tenant_block = f"\n\n## Recruiter Focus\nFocus area: {tc.get('focus_area', 'General')}\nTone: {tc.get('tone', 'supportive')}"
            if tc.get("custom_instructions"):
                tenant_block += f"\nSpecial instructions: {tc['custom_instructions']}"
            if tc.get("key_areas"):
                tenant_block += f"\nKey areas to explore: {', '.join(tc['key_areas'])}"
            if tc.get("must_verify"):
                tenant_block += f"\nMust verify: {', '.join(tc['must_verify'])}"

        user_prompt = get_profile_analyzer_user(
            user_name=state["user_name"],
            life_stage=state["life_stage"],
            resume_json=resume_json,
        ) + tenant_block

        system_prompt = get_profile_analyzer_system()
        contents = [
            {"role": "user", "parts": [{"text": system_prompt}]},
            {"role": "model", "parts": [{"text": "I understand. I will analyze the resume and provide structured insights for the voice interview."}]},
            {"role": "user", "parts": [{"text": user_prompt}]},
        ]

        lf_prompt = get_langfuse_prompt("pipeline/profile-analyzer-system")

        with traced_generation(
            "profile_analyzer",
            model=MODEL,
            prompt=lf_prompt,
            input_data={"system": system_prompt, "user": user_prompt[:2000]},
        ) as gen:
            client = get_gemini_client()
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config={"temperature": 0.3, "response_mime_type": "application/json"},
            )

            usage = getattr(response, "usage_metadata", None)
            gen.update(
                output=response.text,
                usage_details={
                    "input": getattr(usage, "prompt_token_count", 0),
                    "output": getattr(usage, "candidates_token_count", 0),
                } if usage else None,
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
