"""
The MIT License (MIT)

Copyright (c) 2026-present DA-344 (aka Developer Anonymous)

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from ..storage.base import Storage

ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024


def _looks_like_image(head: bytes) -> bool:
    return (
        head.startswith(b"\x89PNG\r\n\x1a\n")
        or head.startswith(b"\xff\xd8\xff")
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


async def store_avatar(storage: Storage, upload: UploadFile) -> str:
    """Validate (extension, declared type and magic bytes) and save; return the key.

    Avatars are served back to other users, so the *content* is checked, not
    just the client-declared content type.
    """
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES or upload.content_type not in ALLOWED_TYPES:
        raise ValueError("Foto no permitida")
    head = await upload.read(12)
    await upload.seek(0)
    if not _looks_like_image(head):
        raise ValueError("Foto no permitida")
    key, _, _data = await storage.save(upload, MAX_AVATAR_SIZE)
    return key


def valid_avatar_key(key: str | None) -> str | None:
    """Reject anything that isn't one of our own generated keys (no path traversal)."""
    if not key or "/" in key or "\\" in key or ".." in key:
        return None
    return key if Path(key).suffix.lower() in ALLOWED_SUFFIXES else None


async def load_avatar(storage: Storage, key: str | None) -> bytes | None:
    valid = valid_avatar_key(key)
    if not valid:
        return None
    try:
        return await storage.read(valid)
    except FileNotFoundError:
        return None


async def remove_stored(storage: Storage, key: str | None) -> None:
    valid = valid_avatar_key(key)
    if valid:
        await storage.delete(valid)
