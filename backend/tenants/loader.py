import json
from pathlib import Path

from interview_prep.schemas import TenantConfig

CONFIGS_DIR = Path(__file__).parent / "configs"


def load_tenant(tenant_id: str) -> TenantConfig:
    config_path = CONFIGS_DIR / f"{tenant_id}.json"
    if not config_path.exists():
        config_path = CONFIGS_DIR / "default.json"

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    raw.setdefault("tenant_id", tenant_id)
    return TenantConfig(**raw)


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
        "focus_area": position.focus_area if position else "General Professional Development",
        "custom_instructions": position.custom_instructions if position else None,
        "position_id": position.id if position else None,
        "position_title": position.title if position else None,
    }
