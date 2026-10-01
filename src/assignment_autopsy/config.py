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

from typing import Literal

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the application configurated via env variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_env: Literal["development", "production", "testing"] = "development"
    app_debug: bool = False
    app_secret_key: str
    app_base_url: AnyHttpUrl
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    database_url: str

    featherless_api_key: str
    featherless_base_url: AnyHttpUrl
    featherless_model: str
    featherless_max_output_tokens: int = 4096
    featherless_max_concurrent_requests: int = 1

    storage_provider: Literal["local", "github"] = "local"
    storage_github_token: str | None = None
    storage_github_repo: str | None = None
    storage_github_branch: str = "main"
    max_upload_size: int = 10 * 1024 * 1024

    session_cookie_name: str = "session"
    session_ttl: int = 7 * 24 * 60 * 60
    session_secure: bool = True
    session_same_site: Literal["lax", "strict", "none"] = "lax"

    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: AnyHttpUrl | None = None


settings = Settings()  # pyright: ignore[reportCallIssue]
