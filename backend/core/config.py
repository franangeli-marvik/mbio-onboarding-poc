import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def get_secret(secret_id: str, fallback_env: str | None = None) -> str | None:
    env_value = os.getenv(fallback_env or secret_id.upper().replace("-", "_"))
    if env_value:
        return env_value

    try:
        from google.cloud import secretmanager

        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "mbio-profile-creation")
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception:
        return None


@lru_cache
def livekit_url() -> str:
    value = get_secret("livekit-url", "LIVEKIT_URL")
    if not value:
        raise ValueError("Missing required secret: LIVEKIT_URL")
    return value


@lru_cache
def livekit_api_key() -> str:
    value = get_secret("livekit-api-key", "LIVEKIT_API_KEY")
    if not value:
        raise ValueError("Missing required secret: LIVEKIT_API_KEY")
    return value


@lru_cache
def livekit_api_secret() -> str:
    value = get_secret("livekit-api-secret", "LIVEKIT_API_SECRET")
    if not value:
        raise ValueError("Missing required secret: LIVEKIT_API_SECRET")
    return value


@lru_cache
def livekit_public_url() -> str:
    return os.getenv("LIVEKIT_PUBLIC_URL", livekit_url())


MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai").lower()
GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "mbio-profile-creation")
GCP_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STORAGE_DRIVER = os.getenv("STORAGE_DRIVER", "local")
DATA_DIR = os.getenv("DATA_DIR", "/data")
