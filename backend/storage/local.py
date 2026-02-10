import json
import os
from pathlib import Path

from core.config import DATA_DIR
from storage.base import StorageDriver


ARTIFACT_FILENAMES = {
    "resume": "resume",
    "transcript": "transcript.json",
    "enhanced_resume": "enhanced_resume.json",
    "session": "session.json",
    "agent_decisions": "agent_decisions.json",
    "audio": "audio.ogg",
}


class LocalStorageDriver(StorageDriver):
    def __init__(self, base_dir: str | None = None):
        self._base = Path(base_dir or DATA_DIR)
        self._base.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, session_id: str) -> Path:
        d = self._base / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_artifact(
        self, session_id: str, artifact_type: str, data: bytes, ext: str
    ) -> str:
        filename = ARTIFACT_FILENAMES.get(artifact_type, f"{artifact_type}.{ext}")
        if not filename.endswith(f".{ext}"):
            filename = f"{artifact_type}.{ext}"
        path = self._session_dir(session_id) / filename
        path.write_bytes(data)
        return str(path)

    def save_json(self, session_id: str, artifact_type: str, payload: dict) -> str:
        filename = ARTIFACT_FILENAMES.get(artifact_type, f"{artifact_type}.json")
        path = self._session_dir(session_id) / filename
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def load_json(self, session_id: str, artifact_type: str) -> dict | None:
        filename = ARTIFACT_FILENAMES.get(artifact_type, f"{artifact_type}.json")
        path = self._session_dir(session_id) / filename
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def load_artifact(self, session_id: str, artifact_type: str) -> bytes | None:
        filename = ARTIFACT_FILENAMES.get(artifact_type, artifact_type)
        path = self._session_dir(session_id) / filename
        if not path.exists():
            return None
        return path.read_bytes()

    def list_sessions(self) -> list[str]:
        if not self._base.exists():
            return []
        return sorted(
            [d.name for d in self._base.iterdir() if d.is_dir()],
            reverse=True,
        )

    def get_artifact_path(self, session_id: str, artifact_type: str) -> str | None:
        filename = ARTIFACT_FILENAMES.get(artifact_type, artifact_type)
        path = self._session_dir(session_id) / filename
        if path.exists():
            return str(path)
        return None
