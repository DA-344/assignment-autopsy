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

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDTimestampMixin


class RubricType(str, Enum):
    POINTS = "points"
    LEVEL = "level"


class Rubric(UUIDTimestampMixin, Base):
    __tablename__ = "rubrics"
    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), unique=True
    )
    type: Mapped[RubricType] = mapped_column(SAEnum(RubricType))
    max_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    levels_descending: Mapped[bool] = mapped_column(default=False)


class RubricCriterion(UUIDTimestampMixin, Base):
    __tablename__ = "rubric_criteria"
    rubric_id: Mapped[UUID] = mapped_column(
        ForeignKey("rubrics.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class RubricLevel(UUIDTimestampMixin, Base):
    __tablename__ = "rubric_levels"
    rubric_id: Mapped[UUID] = mapped_column(
        ForeignKey("rubrics.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer)


class CriterionLevelDescription(UUIDTimestampMixin, Base):
    __tablename__ = "criterion_level_descriptions"
    criterion_id: Mapped[UUID] = mapped_column(
        ForeignKey("rubric_criteria.id", ondelete="CASCADE")
    )
    level_id: Mapped[UUID] = mapped_column(
        ForeignKey("rubric_levels.id", ondelete="CASCADE")
    )
    description: Mapped[str] = mapped_column(Text)
