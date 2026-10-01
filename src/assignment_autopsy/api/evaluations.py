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

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select

from ..app.dependencies import CurrentUser, DBSession
from ..database.models.evaluation import Evaluation
from ..database.models.submission import Submission
from ..database.models.assignment import Assignment
from ..database.models.rubric import Rubric, RubricCriterion, RubricLevel
from ..security.csrf import require_csrf
from ..services.groups import GroupService
from ..services.rubric_scoring import effective_criterion_points, score_level_criterion

router = APIRouter(tags=["evaluations"])


@router.get("/submissions/{submission_id}/evaluation")
async def evaluation_status(submission_id: str, user: CurrentUser, session: DBSession):
    submission = await session.get(Submission, submission_id)
    if not submission or submission.student_id != user.id:
        raise HTTPException(403)
    evaluation = await session.scalar(
        select(Evaluation).where(Evaluation.submission_id == submission.id)
    )
    if not evaluation:
        return JSONResponse({"state": "pending", "result": None})
    return JSONResponse({"state": evaluation.state.value, "result": evaluation.result})


@router.post("/submissions/{submission_id}/official-evaluation")
async def official_evaluation(
    submission_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    official_result: str = Form(""),
    allow_resubmit: bool = Form(False),
    manual_grade: str = Form(""),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)

    submission = await session.get(Submission, submission_id)
    assignment = submission and await session.get(Assignment, submission.assignment_id)

    if not submission:
        raise HTTPException(404, "Submission not found")
    if not assignment:
        raise HTTPException(404, "Assignment not found")

    if not await GroupService(session).admin_group(assignment.group_id, user):
        raise HTTPException(403, "You are not an admin of this group")

    evaluation = await session.scalar(
        select(Evaluation).where(Evaluation.submission_id == submission.id)
    )

    if not evaluation:
        raise HTTPException(
            409, "Todavía no hay una valoración de IA para esta entrega"
        )

    rubric = await session.scalar(
        select(Rubric).where(Rubric.assignment_id == assignment.id)
    )
    criteria = (
        list(
            await session.scalars(
                select(RubricCriterion).where(RubricCriterion.rubric_id == rubric.id)
            )
        )
        if rubric
        else []
    )
    levels = (
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
    form = await request.form()
    rubric_choices = []
    # Criteria can be left without their own weight in the rubric builder; fill the
    # gaps evenly from the rubric total so scoring matches the live preview.
    criterion_points = (
        effective_criterion_points(criteria, rubric.max_points)
        if rubric and rubric.type.value == "level"
        else {}
    )

    for criterion in criteria:
        if rubric and rubric.type.value == "points":
            raw_points = str(form.get(f"rubric_points_{criterion.id}", "")).strip()

            if raw_points:
                try:
                    points = max(
                        0.0,
                        min(
                            float(raw_points),
                            float(criterion.max_points or rubric.max_points or 0),
                        ),
                    )
                except ValueError:
                    points = 0.0

                rubric_choices.append(
                    {
                        "criterion": criterion.label,
                        "level": "Puntos",
                        "points": round(points, 2),
                    }
                )
            continue

        selected_id = str(form.get(f"rubric_choice_{criterion.id}", ""))
        selected = next(
            (level for level in levels if str(level.id) == selected_id), None
        )

        if not selected:
            continue

        position = levels.index(selected)
        points = score_level_criterion(
            criterion_points.get(str(criterion.id), criterion.max_points),
            position,
            len(levels),
            getattr(rubric, "levels_descending", False),
        )
        rubric_choices.append(
            {"criterion": criterion.label, "level": selected.label, "points": points}
        )

    MANUAL_GRADE_MAX = 10.0
    if rubric and rubric.type.value == "level":
        total_max = sum(criterion_points.values()) if criterion_points else 0
    elif rubric:
        total_max = sum((criterion.max_points or 0) for criterion in criteria) or (
            rubric.max_points or 0
        )
    else:
        total_max = 0
    total_earned = (
        sum(choice["points"] for choice in rubric_choices if choice["points"] is not None)
        if rubric_choices
        else None
    )

    if not rubric:
        # No rubric configured: the teacher grades the submission directly.
        raw_manual = manual_grade.strip()
        if raw_manual:
            try:
                total_earned = round(max(0.0, min(float(raw_manual), MANUAL_GRADE_MAX)), 2)
                total_max = MANUAL_GRADE_MAX
            except ValueError:
                pass

    evaluation.official_result = {
        "teacher_selection": official_result,
        "rubric_choices": rubric_choices,
        "total_earned": round(total_earned, 2) if total_earned is not None else None,
        "total_max": total_max or None,
    }
    assignment.allow_resubmit = allow_resubmit

    await session.commit()
    return RedirectResponse(f"/submissions/{submission.id}", status_code=303)
