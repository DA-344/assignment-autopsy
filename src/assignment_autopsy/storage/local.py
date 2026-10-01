"""Disk-backed storage. Simple for local development, but unsuitable for hosts with
an ephemeral filesystem (e.g. Render.com free tier): anything written here is lost
on every redeploy/restart. Use GitHubStorage in production instead.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from .base import Storage


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, upload: UploadFile, maximum: int) -> tuple[str, int, bytes]:
        key = f"{uuid4().hex}{Path(upload.filename or '').suffix.lower()}"
        chunks: list[bytes] = []
        size = 0
        while chunk := await upload.read(65536):
            size += len(chunk)
            if size > maximum:
                raise ValueError("El archivo supera el tamaño permitido")
            chunks.append(chunk)
        data = b"".join(chunks)
        (self.root / key).write_bytes(data)
        return key, size, data

    async def read(self, key: str) -> bytes:
        path = (self.root / key).resolve()
        if path.parent != self.root or not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = (self.root / key).resolve()
        if path.parent == self.root:
            path.unlink(missing_ok=True)
