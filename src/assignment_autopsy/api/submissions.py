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

from pathlib import Path
from urllib.parse import quote
import hashlib

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..app.dependencies import CurrentUser, DBSession
from ..database.models.assignment import Assignment
from ..database.models.evaluation import Evaluation, EvaluationState
from ..database.models.file_asset import FileAsset
from ..database.models.file_asset_view import FileAssetView
from ..database.models.group import Group
from ..database.models.submission import Submission, SubmissionState
from ..database.models.user import UserRole
from ..database.models.rubric import Rubric, RubricCriterion, RubricLevel
from ..security.csrf import require_csrf
from ..services.groups import GroupService
from ..services.rubric_scoring import effective_criterion_points
from ..storage.extractors import extract_text
from ..workers.evaluations import queue_evaluation


def content_disposition(filename: str) -> str:
    """Build a `Content-Disposition` header safe for non-ASCII filenames."""
    ascii_fallback = filename.encode("ascii", "replace").decode("ascii")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"

router = APIRouter(tags=["submissions"])
ALLOWED_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".odt",
    ".odp",
    ".ods",
}


async def _recompute_submission(session: AsyncSession, submission: Submission) -> None:
    """Refresh a submission's derived fields from its current set of files."""
    assets = list(
        await session.scalars(
            select(FileAsset)
            .where(FileAsset.submission_id == submission.id)
            .order_by(FileAsset.created_at)
        )
    )
    submission.original_filename = assets[0].original_filename if assets else "Entrega"
    submission.storage_key = "multi"
    submission.media_type = assets[0].media_type if assets else None
    submission.size = sum(asset.size for asset in assets)
    submission.extracted_text = "\n\n".join(
        asset.extracted_text or "" for asset in assets
    )
    file_hashes = [f"{asset.original_filename}:{asset.sha256}" for asset in assets]
    submission.content_hash = (
        hashlib.sha256("\n".join(sorted(file_hashes)).encode()).hexdigest()
        if file_hashes
        else None
    )


async def _requeue_evaluation(
    session: AsyncSession,
    background_tasks: BackgroundTasks,
    request: Request,
    assignment: Assignment,
    submission: Submission,
) -> None:
    evaluation = await session.scalar(
        select(Evaluation).where(Evaluation.submission_id == submission.id)
    )
    if evaluation:
        evaluation.state = EvaluationState.PENDING
        evaluation.result = None
        evaluation.error = None
    else:
        evaluation = Evaluation(
            submission_id=submission.id, state=EvaluationState.PENDING
        )
        session.add(evaluation)
    await session.commit()
    background_tasks.add_task(
        queue_evaluation,
        request.app.state.session_factory,
        request.app.state.ai_provider,
        evaluation.id,
        assignment,
        submission.extracted_text or "",
    )


@router.get("/assignments/{assignment_id}/submit")
async def submit_form(
    assignment_id: str, request: Request, user: CurrentUser, session: DBSession
):
    assignment = await session.get(Assignment, assignment_id)
    if (
        not assignment
        or await GroupService(session).member_role(assignment.group_id, user)
        != UserRole.STUDENT
    ):
        raise HTTPException(403)
    latest = await session.scalar(
        select(Submission)
        .where(
            Submission.assignment_id == assignment.id, Submission.student_id == user.id
        )
        .order_by(Submission.created_at.desc())
    )
    if (
        latest
        and latest.state == SubmissionState.SUBMITTED
        and not assignment.allow_resubmit
    ):
        raise HTTPException(
            403, "El profesor no ha permitido volver a entregar esta tarea"
        )
    assets = (
        list(
            await session.scalars(
                select(FileAsset).where(FileAsset.submission_id == latest.id)
            )
        )
        if latest
        else []
    )
    group = await session.get(Group, assignment.group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    return request.app.state.templates.TemplateResponse(
        request,
        "submissions/submit.html",
        {
            "assignment": assignment,
            "submission": latest,
            "assets": assets,
            "user": user,
            "breadcrumbs": [
                {"label": group.name, "url": f"/groups/{group.id}"},
                {"label": assignment.title, "url": f"/assignments/{assignment.id}"},
            ],
            "groups": await GroupService(session).visible_to(user),
        },
    )


@router.post("/assignments/{assignment_id}/submit")
async def submit(
    assignment_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    session: DBSession,
    files: list[UploadFile] = File(default=[]),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    assignment = await session.get(Assignment, assignment_id)
    if (
        not assignment
        or await GroupService(session).member_role(assignment.group_id, user)
        != UserRole.STUDENT
    ):
        raise HTTPException(403)
    latest = await session.scalar(
        select(Submission)
        .where(
            Submission.assignment_id == assignment.id, Submission.student_id == user.id
        )
        .order_by(Submission.created_at.desc())
    )
    if (
        latest
        and latest.state == SubmissionState.SUBMITTED
        and not assignment.allow_resubmit
    ):
        raise HTTPException(
            403, "El profesor no ha permitido volver a entregar esta tarea"
        )
    if not files or not any(file.filename for file in files):
        raise HTTPException(422, "Adjunta al menos un archivo")
    submission = (
        latest
        if latest and latest.state == SubmissionState.DRAFT
        else Submission(assignment_id=assignment.id, student_id=user.id)
    )
    if submission.id is None:
        session.add(submission)
        await session.flush()
    for file in files:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(422, "Formato de archivo no permitido")
        key, size, data = await request.app.state.storage.save(
            file, request.app.state.settings.max_upload_size
        )
        session.add(
            FileAsset(
                submission_id=submission.id,
                original_filename=file.filename or "entrega",
                storage_key=key,
                media_type=file.content_type,
                size=size,
                sha256=hashlib.sha256(data).hexdigest(),
                extracted_text=extract_text(data, suffix),
            )
        )
    await session.flush()
    await _recompute_submission(session, submission)
    await _requeue_evaluation(
        session, background_tasks, request, assignment, submission
    )
    return RedirectResponse(f"/submissions/{submission.id}", status_code=303)


async def _authorize_asset(
    session: AsyncSession, asset: FileAsset, user
) -> tuple[bool, Assignment | None]:
    if asset.assignment_id:
        assignment = await session.get(Assignment, asset.assignment_id)
        allowed = bool(
            assignment
            and await GroupService(session).get_member_group(assignment.group_id, user)
        )
        return allowed, assignment
    if asset.submission_id:
        submission = await session.get(Submission, asset.submission_id)
        assignment = submission and await session.get(
            Assignment, submission.assignment_id
        )
        allowed = bool(
            submission
            and assignment
            and (
                submission.student_id == user.id
                or await GroupService(session).teacher_group(assignment.group_id, user)
            )
        )
        return allowed, assignment
    return False, None


async def _enforce_view_once(
    session: AsyncSession, asset: FileAsset, assignment: Assignment | None, user
) -> None:
    """Track per-student consumption of view-once reference files (teachers exempt)."""
    if not (asset.assignment_id and asset.view_once):
        return
    if assignment and await GroupService(session).teacher_group(
        assignment.group_id, user
    ):
        return
    already_viewed = await session.scalar(
        select(FileAssetView).where(
            FileAssetView.file_asset_id == asset.id, FileAssetView.user_id == user.id
        )
    )
    if already_viewed:
        raise HTTPException(410, "Este archivo solo puede verse una vez")
    session.add(FileAssetView(file_asset_id=asset.id, user_id=user.id))
    await session.commit()


@router.get("/files/{file_id}")
async def download_file(
    file_id: str, request: Request, user: CurrentUser, session: DBSession
):
    asset = await session.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(404)
    allowed, assignment = await _authorize_asset(session, asset, user)
    if not allowed or (asset.assignment_id and not asset.downloadable):
        raise HTTPException(403)
    try:
        data = await request.app.state.storage.read(asset.storage_key)
    except FileNotFoundError:
        raise HTTPException(404) from None
    await _enforce_view_once(session, asset, assignment, user)
    return Response(
        content=data,
        media_type=asset.media_type or "application/octet-stream",
        headers={
            "Content-Disposition": content_disposition(asset.original_filename)
        },
    )


@router.get("/files/{file_id}/preview")
async def preview_file(
    file_id: str, request: Request, user: CurrentUser, session: DBSession
):
    asset = await session.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(404)
    allowed, assignment = await _authorize_asset(session, asset, user)
    if not allowed:
        raise HTTPException(403)
    try:
        data = await request.app.state.storage.read(asset.storage_key)
    except FileNotFoundError:
        raise HTTPException(404) from None
    await _enforce_view_once(session, asset, assignment, user)
    if asset.media_type == "application/pdf":
        return Response(content=data, media_type="application/pdf")
    import html

    content = html.escape(
        asset.extracted_text
        or "No hay vista previa de texto disponible para este formato."
    )
    return HTMLResponse(
        f"<title>{html.escape(asset.original_filename)}</title><main style='max-width:900px;margin:40px auto;font:16px system-ui;line-height:1.6'><h1>{html.escape(asset.original_filename)}</h1><pre style='white-space:pre-wrap'>{content}</pre></main>"
    )


@router.post("/files/{file_id}/delete")
async def delete_file(
    file_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    session: DBSession,
    csrf_token: str = Form(),
):
    """Remove a single reference or submission file without touching the rest."""
    require_csrf(request, csrf_token)
    asset = await session.get(FileAsset, file_id)

    if not asset:
        raise HTTPException(404)
    if asset.assignment_id:
        assignment = await session.get(Assignment, asset.assignment_id)

        if not assignment or not await GroupService(session).teacher_group(
            assignment.group_id, user
        ):
            raise HTTPException(403)

        redirect_to = f"/assignments/{assignment.id}/edit"
    elif asset.submission_id:
        submission = await session.get(Submission, asset.submission_id)

        if not submission or submission.student_id != user.id:
            raise HTTPException(403)

        if submission.state != SubmissionState.DRAFT:
            raise HTTPException(403, "No puedes modificar una entrega ya enviada")

        assignment = await session.get(Assignment, submission.assignment_id)
        redirect_to = f"/assignments/{submission.assignment_id}/submit"
    else:
        raise HTTPException(404)

    if not assignment:
        raise HTTPException(404, "Assignment not found")

    await request.app.state.storage.delete(asset.storage_key)
    submission_id = asset.submission_id

    await session.delete(asset)
    await session.flush()

    if submission_id:
        submission = await session.get(Submission, submission_id)

        if not submission:
            raise HTTPException(404, "Submission not found")

        await _recompute_submission(session, submission)
        await _requeue_evaluation(
            session, background_tasks, request, assignment, submission
        )
    else:
        await session.commit()
    return RedirectResponse(redirect_to, status_code=303)


@router.get("/submissions/{submission_id}")
async def submission_detail(
    submission_id: str, request: Request, user: CurrentUser, session: DBSession
):
    submission = await session.get(Submission, submission_id)

    if not submission:
        raise HTTPException(404)

    assignment = await session.get(Assignment, submission.assignment_id)
    member = assignment and await GroupService(session).get_member_group(
        assignment.group_id, user
    )

    if not member:
        raise HTTPException(403, "You are not a member of this group")

    if not assignment:
        raise HTTPException(404, "Assignment not found")

    if not member or (
        submission.student_id != user.id
        and await GroupService(session).teacher_group(assignment.group_id, user) is None
    ):
        raise HTTPException(403)

    evaluation = await session.scalar(
        select(Evaluation).where(Evaluation.submission_id == submission.id)
    )
    assets = list(
        await session.scalars(
            select(FileAsset).where(FileAsset.submission_id == submission.id)
        )
    )
    teacher = (
        assignment is not None
        and await GroupService(session).teacher_group(assignment.group_id, user)
        is not None
    )
    rubric = (
        await session.scalar(
            select(Rubric).where(Rubric.assignment_id == assignment.id)
        )
        if assignment
        else None
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

    criterion_labels = {str(criterion.id): criterion.label for criterion in criteria}
    criterion_points = (
        effective_criterion_points(criteria, rubric.max_points if rubric else None)
        if rubric and rubric.type.value == "level"
        else {}
    )
    group = await session.get(Group, assignment.group_id)

    if not group:
        raise HTTPException(404, "Group not found")

    return request.app.state.templates.TemplateResponse(
        request,
        "submissions/detail.html",
        {
            "submission": submission,
            "assignment": assignment,
            "assets": assets,
            "evaluation": evaluation,
            "teacher": teacher,
            "criterion_labels": criterion_labels,
            "criterion_points": criterion_points,
            "rubric": rubric,
            "criteria": criteria,
            "levels": levels,
            "breadcrumbs": [
                {"label": group.name, "url": f"/groups/{group.id}"},
                {"label": assignment.title, "url": f"/assignments/{assignment.id}"},
            ],
            "groups": await GroupService(session).visible_to(user),
            "user": user,
        },
    )


@router.post("/submissions/{submission_id}/finalize")
async def finalize(
    submission_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    submission = await session.get(Submission, submission_id)
    if not submission or submission.student_id != user.id:
        raise HTTPException(403)
    submission.state = SubmissionState.SUBMITTED
    await session.commit()
    return RedirectResponse(f"/submissions/{submission.id}", status_code=303)
