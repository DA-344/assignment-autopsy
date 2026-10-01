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

from typing import Annotated, Literal

import msgspec


class RequirementResult(msgspec.Struct, frozen=True):
    requirement_id: str
    status: Literal["fulfilled", "missing", "uncertain"] | str
    evidence: list[str]
    explanation: str


class LevelCriterionEstimate(
    msgspec.Struct, tag="level", tag_field="type", frozen=True
):
    criterion_id: str
    estimated_min_level: str
    estimated_max_level: str
    confidence: float
    evidence: list[str]
    explanation: str


class PointsCriterionEstimate(
    msgspec.Struct, tag="points", tag_field="type", frozen=True
):
    criterion_id: str
    estimated_points: float
    max_points: float
    confidence: float
    evidence: list[str]
    explanation: str


CriterionEstimate = Annotated[
    LevelCriterionEstimate | PointsCriterionEstimate, msgspec.Meta()
]


class AIEvaluation(msgspec.Struct, frozen=True):
    requirements: list[RequirementResult]
    rubric: list[CriterionEstimate]
    summary: str
    disclaimer: str
