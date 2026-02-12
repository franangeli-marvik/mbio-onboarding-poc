import hashlib
import json
import logging
from typing import Optional

from interview_prep.schemas import TenantConfig

logger = logging.getLogger(__name__)

_fix_cache: dict[str, TenantConfig] = {}

GEMINI_MODEL = "gemini-2.0-flash"


def _cache_key(tenant_id: str, raw: dict) -> str:
    raw_bytes = json.dumps(raw, sort_keys=True).encode()
    digest = hashlib.sha256(raw_bytes).hexdigest()[:16]
    return f"{tenant_id}:{digest}"


def fix_tenant_config(raw: dict, tenant_id: str) -> Optional[TenantConfig]:
    key = _cache_key(tenant_id, raw)
    if key in _fix_cache:
        logger.info("Tenant config fix cache hit for %s", tenant_id)
        return _fix_cache[key]

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
        _fix_cache[key] = config
        logger.info("Gemini auto-fixed tenant config for %s", tenant_id)
        return config

    except Exception as e:
        logger.warning("Gemini auto-fix failed for tenant %s: %s", tenant_id, e)
        return None
