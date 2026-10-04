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

from uuid import UUID
from typing import TYPE_CHECKING

import httpx
import msgspec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..database.models.assignment import Assignment
from ..database.models.evaluation import Evaluation, EvaluationState
from ..database.models.rubric import Rubric, RubricCriterion, RubricLevel
from ..database.models.file_asset import FileAsset
from ..database.models.submission import Submission

if TYPE_CHECKING:
    from ..ai.provider import AIProvider


async def queue_evaluation(
    session_factory: async_sessionmaker,
    provider: AIProvider,
    evaluation_id: UUID,
    assignment: Assignment,
    submission_text: str,
) -> None:
    """Build a database-backed job payload after the HTTP response is returned."""
    async with session_factory() as session:
        evaluation: Evaluation | None = await session.get(Evaluation, evaluation_id)
        current_submission: Submission | None = (
            await session.get(Submission, evaluation.submission_id)
            if evaluation
            else None
        )
        if current_submission and current_submission.content_hash:
            assert evaluation is not None
            cached: Evaluation | None = await session.scalar(
                select(Evaluation)
                .join(Submission, Submission.id == Evaluation.submission_id)
                .where(
                    Submission.content_hash == current_submission.content_hash,
                    Evaluation.id != evaluation_id,
                    Evaluation.state == EvaluationState.COMPLETED,
                )
                .order_by(Evaluation.created_at.desc())
            )
            if cached:
                evaluation.result = cached.result
                evaluation.state = EvaluationState.COMPLETED
                await session.commit()
                return
        rubric: Rubric | None = await session.scalar(
            select(Rubric).where(Rubric.assignment_id == assignment.id)
        )
        criteria: list[RubricCriterion] = (
            list(
                await session.scalars(
                    select(RubricCriterion).where(
                        RubricCriterion.rubric_id == rubric.id
                    )
                )
            )
            if rubric
            else []
        )
        levels: list[RubricLevel] = (
            list(
                await session.scalars(
                    select(RubricLevel)
                    .where(RubricLevel.rubric_id == rubric.id)
                    .order_by(RubricLevel.position)
                )
            )
            if rubric
            else []
        )
        references: list[FileAsset] = list(
            await session.scalars(
                select(FileAsset).where(
                    FileAsset.assignment_id == assignment.id,
                    FileAsset.use_for_ai.is_(True),
                )
            )
        )
    reference_text = "\n\n".join(item.extracted_text or "" for item in references)
    payload = {
        "task": assignment.description or "",
        "requirements": assignment.requirements,
        "reference_material": reference_text,
        "rubric": {
            "type": rubric.type.value if rubric else "level",
            "criteria": [
                {"id": str(item.id), "label": item.label, "max_points": item.max_points}
                for item in criteria
            ],
            "levels": [{"id": str(item.id), "label": item.label} for item in levels],
        },
        "submission_text": submission_text,
    }
    await run_evaluation(session_factory, evaluation_id, provider, payload)


async def run_evaluation(
    session_factory: async_sessionmaker, evaluation_id: UUID, provider: AIProvider, payload: dict
) -> None:
    """Execute one job and persist a validated provider result or its error."""
    async with session_factory() as session:
        evaluation = await session.get(Evaluation, evaluation_id)
        if not evaluation:
            return
        evaluation.state = EvaluationState.PROCESSING
        await session.commit()
        try:
            result = await provider.evaluate_submission(**payload)
            evaluation.result = __import__("msgspec").to_builtins(result)
            evaluation.state = EvaluationState.COMPLETED
            evaluation.error = None
        except (ValueError, KeyError, httpx.HTTPError, msgspec.DecodeError) as exc:
            evaluation.state = EvaluationState.FAILED
            evaluation.error = str(exc)[:1000]
        await session.commit()
