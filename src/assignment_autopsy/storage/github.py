"""Stores files as raw blobs in a private GitHub repository, used as a free CDN.

Hosts like Render.com have an ephemeral filesystem: anything written to local
disk is lost on every redeploy or restart. Rather than requiring a paid object
storage bucket, files are committed to a private GitHub repository through the
Contents API and read back the same way - durable across deploys, free, and
independent of the app's own disk.
"""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import UploadFile

from .base import Storage

API_BASE = "https://api.github.com"


class GitHubStorage(Storage):
    def __init__(self, token: str, repo: str, branch: str = "main") -> None:
        self.repo = repo
        self.branch = branch
        self._client = httpx.AsyncClient(
            base_url=API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=httpx.Timeout(30.0),
        )

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
        response = await self._client.put(
            f"/repos/{self.repo}/contents/{key}",
            json={
                "message": f"upload {key}",
                "content": base64.b64encode(data).decode("ascii"),
                "branch": self.branch,
            },
        )
        response.raise_for_status()
        return key, size, data

    async def read(self, key: str) -> bytes:
        response = await self._client.get(
            f"/repos/{self.repo}/contents/{key}",
            params={"ref": self.branch},
            headers={"Accept": "application/vnd.github.raw"},
        )
        if response.status_code == 404:
            raise FileNotFoundError(key)
        response.raise_for_status()
        return response.content

    async def delete(self, key: str) -> None:
        lookup = await self._client.get(
            f"/repos/{self.repo}/contents/{key}", params={"ref": self.branch}
        )
        if lookup.status_code == 404:
            return
        lookup.raise_for_status()
        response = await self._client.request(
            "DELETE",
            f"/repos/{self.repo}/contents/{key}",
            json={
                "message": f"delete {key}",
                "sha": lookup.json()["sha"],
                "branch": self.branch,
            },
        )
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
