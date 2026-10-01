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

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDTimestampMixin


class UserRole(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"


class User(UUIDTimestampMixin, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    last_username_change_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    avatar_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    google_subject: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    totp_secret_encrypted: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    recovery_code_hashes: Mapped[list[str]] = mapped_column(
        __import__("sqlalchemy").JSON, default=list
    )
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.STUDENT)
