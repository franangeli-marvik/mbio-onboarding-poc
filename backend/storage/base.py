from abc import ABC, abstractmethod


class StorageDriver(ABC):
    @abstractmethod
    def save_artifact(
        self, session_id: str, artifact_type: str, data: bytes, ext: str
    ) -> str: ...

    @abstractmethod
    def save_json(self, session_id: str, artifact_type: str, payload: dict) -> str: ...

    @abstractmethod
    def load_json(self, session_id: str, artifact_type: str) -> dict | None: ...

    @abstractmethod
    def load_artifact(self, session_id: str, artifact_type: str) -> bytes | None: ...

    @abstractmethod
    def list_sessions(self) -> list[str]: ...

    @abstractmethod
    def get_artifact_path(self, session_id: str, artifact_type: str) -> str | None: ...
