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

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from ..app.dependencies import CurrentUser, DBSession
from ..database.models.membership import Membership
from ..database.models.user import User, UserRole
from ..database.models.assignment import Assignment
from ..security.csrf import require_csrf
from ..services.avatars import remove_stored, store_avatar
from ..services.groups import GroupService, InvitesPausedError
from sqlalchemy import select

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("")
async def list_groups(request: Request, user: CurrentUser, session: DBSession):
    groups = await GroupService(session).visible_to(user)
    return request.app.state.templates.TemplateResponse(
        request, "groups/list.html", {"groups": groups, "user": user}
    )


@router.post("")
async def create_group(
    request: Request,
    user: CurrentUser,
    session: DBSession,
    name: str = Form(),
    description: str = Form(""),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    if not name.strip():
        raise HTTPException(422, "El nombre del equipo es obligatorio")
    group = await GroupService(session).create(user, name.strip(), description)
    return RedirectResponse(f"/groups/{group.id}", status_code=303)


@router.post("/join")
async def join_group(
    request: Request,
    user: CurrentUser,
    session: DBSession,
    code: str = Form(),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    # Accept a pasted invitation link as well as the bare code.
    try:
        group = await GroupService(session).join_invite(
            code.strip().rstrip("/").rsplit("/", 1)[-1], user
        )
    except InvitesPausedError:
        raise HTTPException(
            403, "El profesor ha pausado las invitaciones de este equipo"
        ) from None
    if not group:
        raise HTTPException(404, "Código de invitación no válido")
    return RedirectResponse(f"/groups/{group.id}", status_code=303)


@router.get("/{group_id}")
async def group_detail(
    group_id: str, request: Request, user: CurrentUser, session: DBSession
):
    group = await GroupService(session).get_member_group(group_id, user)
    if not group:
        raise HTTPException(404, "Grupo no encontrado")
    assignments = list(
        await session.scalars(
            select(Assignment)
            .where(Assignment.group_id == group.id)
            .order_by(Assignment.created_at.desc())
        )
    )
    admin = await GroupService(session).teacher_group(group_id, user) is not None
    invite_creator = (
        await session.get(User, group.invite_created_by or group.created_by)
        if group.invite_code
        else None
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "groups/detail.html",
        {
            "group": group,
            "assignments": assignments,
            "members": await GroupService(session).members_with_roles(group),
            "admin": admin,
            "is_creator": group.created_by == user.id,
            "invite_creator": invite_creator,
            "user": user,
        },
    )


@router.post("/{group_id}/settings")
async def update_group(
    group_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    name: str = Form(),
    description: str = Form(""),
    avatar: UploadFile | None = File(None),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    service = GroupService(session)
    group = await service.admin_group(group_id, user)
    if not group:
        raise HTTPException(403, "Solo un profesor del equipo puede administrarlo")
    if not name.strip():
        raise HTTPException(422, "El nombre del equipo es obligatorio")
    storage = request.app.state.storage
    avatar_key = None
    if avatar and avatar.filename:
        try:
            avatar_key = await store_avatar(storage, avatar)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    previous = group.avatar_key
    await service.update(
        group, name=name, description=description, avatar_key=avatar_key
    )
    if avatar_key:
        await remove_stored(storage, previous)
    return RedirectResponse(f"/groups/{group.id}", status_code=303)


@router.post("/{group_id}/delete")
async def delete_group(
    group_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    group = await GroupService(session).admin_group(group_id, user)
    if not group or group.created_by != user.id:
        raise HTTPException(403, "Solo quien creó el equipo puede eliminarlo")
    await session.delete(group)
    await session.commit()
    return RedirectResponse("/groups", status_code=303)


@router.post("/{group_id}/invite")
async def generate_invite(
    group_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    group = await GroupService(session).admin_group(group_id, user)
    if not group:
        raise HTTPException(403)
    await GroupService(session).generate_invite(group, user)
    return RedirectResponse(f"/groups/{group.id}#group-settings/invites", status_code=303)


@router.post("/{group_id}/invite/pause")
async def toggle_invite_pause(
    group_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    group = await GroupService(session).admin_group(group_id, user)
    if not group:
        raise HTTPException(403)
    await GroupService(session).set_invites_paused(group, not group.invites_paused)
    return RedirectResponse(f"/groups/{group.id}#group-settings/invites", status_code=303)


@router.post("/{group_id}/members/{member_id}/role")
async def update_member_role(
    group_id: str,
    member_id: str,
    request: Request,
    user: CurrentUser,
    session: DBSession,
    role: UserRole = Form(),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    group = await GroupService(session).admin_group(group_id, user)
    if not group or str(group.created_by) == member_id:
        raise HTTPException(403, "Solo el creador puede administrar miembros")
    membership = await session.scalar(
        select(Membership).where(
            Membership.group_id == group.id, Membership.user_id == member_id
        )
    )
    if not membership:
        raise HTTPException(404, "Miembro no encontrado")
    membership.role = role
    await session.commit()
    return RedirectResponse(f"/groups/{group.id}", status_code=303)
