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
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from ..app.dependencies import CurrentUser, DBSession
from ..database.models.assignment import Assignment
from ..database.models.evaluation import Evaluation, EvaluationState
from ..database.models.file_asset import FileAsset
from ..database.models.group import Group
from ..database.models.submission import Submission, SubmissionState
from ..database.models.user import User
from ..database.models.rubric import (
    CriterionLevelDescription,
    Rubric,
    RubricCriterion,
    RubricLevel,
    RubricType,
)
from ..security.csrf import require_csrf
from ..storage.extractors import extract_text
from ..services.groups import GroupService
from ..services.rubric_scoring import estimate_ai_grade

router = APIRouter(tags=["assignments"])


def _parse_due_at(raw: str) -> datetime | None:
    """Parse a `datetime-local` value, tolerating anything the browser sends."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


@router.get("/groups/{group_id}/assignments")
async def list_assignments(group_id: str, user: CurrentUser, session: DBSession):
    if not await GroupService(session).get_member_group(group_id, user):
        raise HTTPException(404)
    return RedirectResponse(f"/groups/{group_id}", status_code=303)


@router.get("/groups/{group_id}/assignments/create")
async def create_form(
    group_id: str, request: Request, user: CurrentUser, session: DBSession
):
    if not await GroupService(session).admin_group(group_id, user):
        raise HTTPException(403)

    group = await session.get(Group, group_id)

    if not group:
        raise HTTPException(404, "Group not found")

    return request.app.state.templates.TemplateResponse(
        request,
        "assignments/create.html",
        {
            "group_id": group_id,
            "breadcrumbs": [{"label": group.name, "url": f"/groups/{group_id}"}],
            "groups": await GroupService(session).visible_to(user),
            "user": user,
        },
    )


@router.post("/groups/{group_id}/assignments")
async def create_assignment(
    group_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    title: str = Form(),
    description: str | None = Form(None),
    requirements: str = Form(""),
    due_at: str = Form(""),
    rubric_enabled: bool = Form(False),
    rubric_type: RubricType = Form(RubricType.LEVEL),
    max_points: int = Form(100),
    criterion_label: list[str] = Form(default=[]),
    criterion_points: list[str] = Form(default=[]),
    level_label: list[str] = Form(default=[]),
    chat_enabled: bool = Form(False),
    allow_resubmit: bool = Form(False),
    criteria: str | None = Form(None),
    levels: str | None = Form(None),
    reference_files: list[UploadFile] = File(default=[]),
    reference_downloadable: bool = Form(True),
    reference_view_once: bool = Form(False),
    reference_use_for_ai: bool = Form(False),
    levels_descending: bool = Form(False),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    if not await GroupService(session).admin_group(group_id, user):
        raise HTTPException(403)
    if not title.strip():
        raise HTTPException(422, "El título es obligatorio")
    reqs = [
        {"id": str(i + 1), "text": line.strip()}
        for i, line in enumerate(requirements.splitlines())
        if line.strip()
    ]
    due = _parse_due_at(due_at)
    legacy_criteria = [
        item.strip() for item in (criteria or "").splitlines() if item.strip()
    ]
    legacy_levels = [item.strip() for item in (levels or "").split("|") if item.strip()]
    rubric_enabled = rubric_enabled or bool(legacy_criteria or legacy_levels)
    if not criterion_label and legacy_criteria:
        criterion_label = legacy_criteria
    if not level_label and legacy_levels:
        level_label = legacy_levels
    assignment = Assignment(
        group_id=group_id,
        title=title,
        description=description,
        requirements=reqs,
        due_at=due,
        chat_enabled=chat_enabled,
        allow_resubmit=allow_resubmit,
        created_by=user.id,
    )
    session.add(assignment)
    await session.flush()
    for upload in reference_files:
        if not upload.filename:
            continue
        key, size, data = await request.app.state.storage.save(
            upload, request.app.state.settings.max_upload_size
        )
        suffix = Path(upload.filename).suffix.lower()
        session.add(
            FileAsset(
                assignment_id=assignment.id,
                original_filename=upload.filename,
                storage_key=key,
                media_type=upload.content_type,
                size=size,
                sha256=__import__("hashlib").sha256(data).hexdigest(),
                extracted_text=extract_text(data, suffix),
                downloadable=reference_downloadable,
                view_once=reference_view_once,
                use_for_ai=reference_use_for_ai,
            )
        )
    if rubric_enabled:
        rubric = Rubric(
            assignment_id=assignment.id,
            type=rubric_type,
            max_points=max_points if rubric_type == RubricType.POINTS else None,
            levels_descending=levels_descending,
        )
        session.add(rubric)
        await session.flush()
        rubric_criteria: list[RubricCriterion] = []
        criteria_rows = []
        for position, label in enumerate(criterion_label):
            label = label.strip()
            if not label:
                continue
            points = None
            if position < len(criterion_points) and criterion_points[position].strip():
                try:
                    points = int(float(criterion_points[position]))
                except ValueError:
                    points = None
            criterion = RubricCriterion(
                rubric_id=rubric.id, label=label, position=position, max_points=points
            )
            session.add(criterion)
            rubric_criteria.append(criterion)
            criteria_rows.append((position, criterion))
        rubric_levels: list[RubricLevel] = []
        if rubric_type == RubricType.LEVEL:
            for position, label in enumerate(level_label):
                label = label.strip()
                if label:
                    level = RubricLevel(
                        rubric_id=rubric.id, label=label, position=position
                    )
                    session.add(level)
                    rubric_levels.append(level)
            await session.flush()
            form = await request.form()
            for row, criterion in criteria_rows:
                for column, level in enumerate(rubric_levels):
                    description = str(
                        form.get(f"rubric_cell_{row}_{column}", "")
                    ).strip()
                    if description:
                        session.add(
                            CriterionLevelDescription(
                                criterion_id=criterion.id,
                                level_id=level.id,
                                description=description,
                            )
                        )
    await session.commit()
    return RedirectResponse(f"/assignments/{assignment.id}", status_code=303)


@router.get("/assignments/{assignment_id}")
async def assignment_detail(
    assignment_id: str, request: Request, user: CurrentUser, session: DBSession
):
    assignment = await session.get(Assignment, assignment_id)
    group_service = GroupService(session)
    group = assignment and await group_service.get_member_group(
        assignment.group_id, user
    )
    if not assignment or not group:
        raise HTTPException(404)
    member_role = await group_service.member_role(assignment.group_id, user)
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
    descriptions = (
        list(
            await session.scalars(
                select(CriterionLevelDescription).where(
                    CriterionLevelDescription.criterion_id.in_(
                        [criterion.id for criterion in criteria]
                    )
                )
            )
        )
        if criteria
        else []
    )
    cell_descriptions = {
        (str(item.criterion_id), str(item.level_id)): item.description
        for item in descriptions
    }
    references = list(
        await session.scalars(
            select(FileAsset).where(FileAsset.assignment_id == assignment.id)
        )
    )
    latest_submission = (
        await session.scalar(
            select(Submission)
            .where(
                Submission.assignment_id == assignment.id,
                Submission.student_id == user.id,
            )
            .order_by(Submission.created_at.desc())
        )
        if member_role and member_role.value == "student"
        else None
    )
    submissions = []
    if member_role and member_role.value == "teacher":
        rows = (
            await session.execute(
                select(Submission, User, Evaluation)
                .join(User, User.id == Submission.student_id)
                .outerjoin(Evaluation, Evaluation.submission_id == Submission.id)
                .where(
                    Submission.assignment_id == assignment.id,
                    Submission.state == SubmissionState.SUBMITTED,
                )
                .order_by(Submission.created_at.desc())
            )
        ).all()
        for submission_row, student, submission_evaluation in rows:
            ai_grade = None
            if (
                submission_evaluation
                and submission_evaluation.state == EvaluationState.COMPLETED
            ):
                ai_grade = estimate_ai_grade(
                    rubric, criteria, levels, submission_evaluation.result
                )
            submissions.append(
                {
                    "submission": submission_row,
                    "student": student,
                    "ai_grade": ai_grade,
                }
            )
    criterion_labels = {str(criterion.id): criterion.label for criterion in criteria}
    return request.app.state.templates.TemplateResponse(
        request,
        "assignments/detail.html",
        {
            "assignment": assignment,
            "references": references,
            "submission": latest_submission,
            "submissions": submissions,
            "criterion_labels": criterion_labels,
            "rubric": rubric,
            "criteria": criteria,
            "levels": levels,
            "cell_descriptions": cell_descriptions,
            "member_role": member_role,
            "breadcrumbs": [{"label": group.name, "url": f"/groups/{group.id}"}],
            "groups": await group_service.visible_to(user),
            "user": user,
        },
    )


@router.get("/assignments/{assignment_id}/edit")
async def edit_assignment_form(
    assignment_id: str, request: Request, user: CurrentUser, session: DBSession
):
    assignment = await session.get(Assignment, assignment_id)
    group = assignment and await GroupService(session).teacher_group(
        assignment.group_id, user
    )
    if not assignment or not group:
        raise HTTPException(403)
    references = list(
        await session.scalars(
            select(FileAsset).where(FileAsset.assignment_id == assignment.id)
        )
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "assignments/edit.html",
        {
            "assignment": assignment,
            "references": references,
            "breadcrumbs": [
                {"label": group.name, "url": f"/groups/{group.id}"},
                {"label": assignment.title, "url": f"/assignments/{assignment.id}"},
            ],
            "groups": await GroupService(session).visible_to(user),
            "user": user,
        },
    )


@router.post("/assignments/{assignment_id}/edit")
async def edit_assignment(
    assignment_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    title: str = Form(),
    description: str | None = Form(None),
    requirements: str = Form(""),
    due_at: str = Form(""),
    chat_enabled: bool = Form(False),
    allow_resubmit: bool = Form(False),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    assignment = await session.get(Assignment, assignment_id)
    if not assignment or not await GroupService(session).teacher_group(
        assignment.group_id, user
    ):
        raise HTTPException(403)
    if not title.strip():
        raise HTTPException(422, "El título es obligatorio")
    assignment.title = title.strip()
    assignment.description = description.strip() if description else None
    assignment.requirements = [
        {"id": str(index + 1), "text": line.strip()}
        for index, line in enumerate(requirements.splitlines())
        if line.strip()
    ]
    assignment.due_at = _parse_due_at(due_at)
    assignment.chat_enabled = chat_enabled
    assignment.allow_resubmit = allow_resubmit
    await session.commit()
    return RedirectResponse(f"/assignments/{assignment.id}", status_code=303)


@router.post("/assignments/{assignment_id}/references")
async def add_reference_files(
    assignment_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    reference_files: list[UploadFile] = File(default=[]),
    reference_downloadable: bool = Form(True),
    reference_view_once: bool = Form(False),
    reference_use_for_ai: bool = Form(False),
    csrf_token: str = Form(),
):
    """Append reference files to an existing assignment without touching the rest."""
    require_csrf(request, csrf_token)
    assignment = await session.get(Assignment, assignment_id)
    if not assignment or not await GroupService(session).teacher_group(
        assignment.group_id, user
    ):
        raise HTTPException(403)
    for upload in reference_files:
        if not upload.filename:
            continue
        key, size, data = await request.app.state.storage.save(
            upload, request.app.state.settings.max_upload_size
        )
        suffix = Path(upload.filename).suffix.lower()
        session.add(
            FileAsset(
                assignment_id=assignment.id,
                original_filename=upload.filename,
                storage_key=key,
                media_type=upload.content_type,
                size=size,
                sha256=__import__("hashlib").sha256(data).hexdigest(),
                extracted_text=extract_text(data, suffix),
                downloadable=reference_downloadable,
                view_once=reference_view_once,
                use_for_ai=reference_use_for_ai,
            )
        )
    await session.commit()
    return RedirectResponse(f"/assignments/{assignment.id}/edit", status_code=303)


@router.post("/assignments/{assignment_id}/delete")
async def delete_assignment(
    assignment_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    assignment = await session.get(Assignment, assignment_id)
    if not assignment or not await GroupService(session).teacher_group(
        assignment.group_id, user
    ):
        raise HTTPException(403)
    group_id = assignment.group_id
    await session.delete(assignment)
    await session.commit()
    return RedirectResponse(f"/groups/{group_id}", status_code=303)
