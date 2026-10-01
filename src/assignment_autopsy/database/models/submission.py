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

from enum import Enum
from uuid import UUID

from sqlalchemy import Enum as SAEnum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDTimestampMixin


class SubmissionState(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"


class Submission(UUIDTimestampMixin, Base):
    __tablename__ = "submissions"
    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255), default="Entrega")
    storage_key: Mapped[str] = mapped_column(String(500), default="")
    media_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size: Mapped[int] = mapped_column(default=0)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    state: Mapped[SubmissionState] = mapped_column(
        SAEnum(SubmissionState), default=SubmissionState.DRAFT
    )
