import os
from functools import lru_cache

from core.config import get_secret


@lru_cache
def get_gemini_client():
    from google import genai

    api_key = get_secret("gemini-api-key", "GEMINI_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    return genai.Client()


@lru_cache
def get_openai_client():
    from openai import OpenAI

    return OpenAI()


def get_langfuse_client():
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3333")

    if not public_key or not secret_key:
        return None

    try:
        from langfuse import Langfuse

        return Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    except Exception:
        return None
