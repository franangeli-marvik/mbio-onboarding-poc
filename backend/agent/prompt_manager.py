import logging
from functools import lru_cache
from typing import Any

from core.clients import get_langfuse_client

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _langfuse():
    return get_langfuse_client()


def get_prompt(name: str, *, fallback: str, label: str = "production", **variables) -> str:
    client = _langfuse()
    if client is None:
        if variables:
            return _compile_fallback(fallback, variables)
        return fallback

    try:
        prompt = client.get_prompt(name, label=label, type="text")
        compiled = prompt.compile(**variables) if variables else prompt.compile()
        logger.info("Prompt '%s' fetched from Langfuse (version=%s)", name, prompt.version)
        return compiled
    except Exception as e:
        logger.warning("Langfuse prompt '%s' unavailable (%s), using fallback", name, e)
        if variables:
            return _compile_fallback(fallback, variables)
        return fallback


def get_langfuse_prompt(name: str, *, label: str = "production") -> Any | None:
    client = _langfuse()
    if client is None:
        return None
    try:
        return client.get_prompt(name, label=label, type="text")
    except Exception:
        return None


def _compile_fallback(template: str, variables: dict) -> str:
    result = template
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result
