import json
import logging
from typing import Optional

from interview_prep.schemas import TenantConfig

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"


def _persist_fixed_config(tenant_id: str, fixed_config: dict) -> None:
    try:
        from core.clients import get_langfuse_client

        client = get_langfuse_client()
        if client is None:
            return

        prompt_name = f"tenant/{tenant_id}"
        client.create_prompt(
            name=prompt_name,
            type="text",
            prompt=f"Auto-corrected config for {tenant_id}",
            config=fixed_config,
            labels=["production"],
        )
        logger.info(
            "Persisted auto-fixed config to Langfuse for %s (new version created)",
            tenant_id,
        )
    except Exception as e:
        logger.warning("Failed to persist fixed config to Langfuse for %s: %s", tenant_id, e)


def fix_tenant_config(raw: dict, tenant_id: str) -> Optional[TenantConfig]:
    try:
        from core.clients import get_gemini_client

        client = get_gemini_client()
        schema = TenantConfig.model_json_schema()

        prompt = (
            "You are given a malformed or incomplete tenant configuration JSON "
            "and the expected Pydantic schema. Fix the JSON so it conforms to the "
            "schema exactly. Preserve all original values where possible. "
            "Fill in reasonable defaults for any missing required fields.\n\n"
            f"Expected schema:\n```json\n{json.dumps(schema, indent=2)}\n```\n\n"
            f"Malformed input:\n```json\n{json.dumps(raw, indent=2)}\n```\n\n"
            f"The tenant_id is: {tenant_id}\n\n"
            "Return ONLY the corrected JSON object."
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config={"temperature": 0.0, "response_mime_type": "application/json"},
        )

        fixed = json.loads(response.text)
        fixed.setdefault("tenant_id", tenant_id)
        config = TenantConfig(**fixed)
        logger.info("Gemini auto-fixed tenant config for %s", tenant_id)

        _persist_fixed_config(tenant_id, config.model_dump(mode="json"))

        return config

    except Exception as e:
        logger.warning("Gemini auto-fix failed for tenant %s: %s", tenant_id, e)
        return None
