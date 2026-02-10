import os

from storage.base import StorageDriver
from storage.local import LocalStorageDriver


def get_storage() -> StorageDriver:
    driver = os.getenv("STORAGE_DRIVER", "local")
    if driver == "local":
        return LocalStorageDriver()
    raise ValueError(f"Unknown storage driver: {driver}")
