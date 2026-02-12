import json
import logging
from pathlib import Path

from interview_prep.schemas import TenantConfig

logger = logging.getLogger(__name__)

CONFIGS_DIR = Path(__file__).parent / "configs"


def _load_from_langfuse(tenant_id: str) -> TenantConfig | None:
    try:
        from core.clients import get_langfuse_client

        client = get_langfuse_client()
        if client is None:
            return None

        prompt = client.get_prompt(
            f"tenant/{tenant_id}", label="production", type="text"
        )
        config_json = getattr(prompt, "config", None)
        if not config_json or not isinstance(config_json, dict):
            logger.warning("Langfuse tenant/%s has no valid config JSON", tenant_id)
            return None

        config_json.setdefault("tenant_id", tenant_id)

        try:
            return TenantConfig(**config_json)
        except Exception as validation_err:
            logger.warning(
                "Langfuse tenant/%s config invalid (%s), attempting auto-fix",
                tenant_id,
                validation_err,
            )
            from tenants.config_fixer import fix_tenant_config

            return fix_tenant_config(config_json, tenant_id)

    except Exception as e:
        logger.debug("Langfuse tenant/%s not available: %s", tenant_id, e)
        return None


def _load_from_file(tenant_id: str) -> TenantConfig:
    config_path = CONFIGS_DIR / f"{tenant_id}.json"
    if not config_path.exists():
        config_path = CONFIGS_DIR / "default.json"

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    raw.setdefault("tenant_id", tenant_id)
    return TenantConfig(**raw)


def load_tenant(tenant_id: str) -> TenantConfig:
    config = _load_from_langfuse(tenant_id)
    if config is not None:
        logger.info("Loaded tenant %s from Langfuse", tenant_id)
        return config

    logger.info("Falling back to local JSON for tenant %s", tenant_id)
    return _load_from_file(tenant_id)


def resolve_position(tenant: TenantConfig, position_id: str | None = None) -> dict:
    position = None
    if position_id:
        position = next(
            (p for p in tenant.positions if p.id == position_id),
            None,
        )
    if position is None and tenant.positions:
        position = tenant.positions[0]

    return {
        "tenant_id": tenant.tenant_id,
        "company_name": tenant.company_name,
        "tone": tenant.tone,
        "industry": tenant.industry,
        "description": tenant.description,
        "focus_area": position.focus_area if position else "General Professional Development",
        "custom_instructions": position.custom_instructions if position else None,
        "position_id": position.id if position else None,
        "position_title": position.title if position else None,
        "key_areas": position.key_areas if position else [],
        "must_verify": position.must_verify if position else [],
    }
