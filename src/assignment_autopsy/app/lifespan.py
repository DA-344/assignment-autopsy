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

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
import httpx

from ..config import settings
from ..ai.featherless import FeatherlessProvider
from ..database.session import SessionLocal
from ..storage.base import Storage
from ..storage.github import GitHubStorage
from ..storage.local import LocalStorage


def _build_storage() -> Storage:
    """Pick the storage backend from `storage_provider`.

    `local` writes to the `uploads/` folder - fine for development, but lost on
    every redeploy on hosts with an ephemeral filesystem (e.g. Render.com).
    `github` commits files to a private GitHub repo instead, which survives
    redeploys and costs nothing.
    """
    if settings.storage_provider == "github":
        if not settings.storage_github_token or not settings.storage_github_repo:
            raise RuntimeError(
                "storage_provider=github requires storage_github_token and "
                "storage_github_repo"
            )
        return GitHubStorage(
            settings.storage_github_token,
            settings.storage_github_repo,
            settings.storage_github_branch,
        )
    return LocalStorage(Path("uploads"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.http_client = httpx.AsyncClient(
        base_url=str(settings.featherless_base_url),
        headers={
            "Authorization": f"Bearer {settings.featherless_api_key}",
            "HTTP-Referer": str(settings.app_base_url),
            "X-Title": "Assignment Autopsy",
        },
        timeout=httpx.Timeout(90.0),
    )
    app.state.storage = _build_storage()
    app.state.session_factory = SessionLocal
    app.state.ai_provider = FeatherlessProvider(app.state.http_client, settings)
    yield
    await app.state.http_client.aclose()
    if isinstance(app.state.storage, GitHubStorage):
        await app.state.storage.aclose()
