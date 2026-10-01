"""Storage backend contract shared by local disk and remote (GitHub CDN) providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import UploadFile


class Storage(ABC):
    """Common interface so API routes never need to know which backend is active."""

    @abstractmethod
    async def save(self, upload: UploadFile, maximum: int) -> tuple[str, int, bytes]:
        """Persist `upload` (rejecting it past `maximum` bytes); return (key, size, raw bytes)."""

    @abstractmethod
    async def read(self, key: str) -> bytes:
        """Return the raw bytes stored under `key`; raise FileNotFoundError if missing."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the object stored under `key`, if it exists."""
