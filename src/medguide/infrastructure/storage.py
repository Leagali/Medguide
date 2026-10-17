import hashlib
import os
import re
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class RawStorage(Protocol):
    def put(self, data: bytes) -> tuple[str, str]: ...
    def read(self, key: str) -> bytes: ...


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{2}/[a-f0-9]{64}", key):
            raise ValueError("Invalid storage key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Storage path escapes root")
        return path

    def put(self, data: bytes) -> tuple[str, str]:
        digest = hashlib.sha256(data).hexdigest()
        key = f"{digest[:2]}/{digest}"
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise OSError("Storage integrity failure")
            return key, digest
        temporary = path.with_name(f".{digest}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return key, digest

    def read(self, key: str) -> bytes:
        data = self.path(key).read_bytes()
        if hashlib.sha256(data).hexdigest() != key.split("/")[1]:
            raise OSError("Storage integrity failure")
        return data
