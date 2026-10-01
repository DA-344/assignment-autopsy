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

from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database.session import get_session
from ..database.models.assignment import Assignment
from ..database.models.group import Group
from ..database.models.membership import Membership
from ..database.models.session import Session
from ..database.models.user import User, UserRole
from ..security.sessions import hash_session_token

DBSession = Annotated[AsyncSession, Depends(get_session)]


def _login_redirect(request: Request) -> HTTPException:
    destination = (
        f"{request.url.path}?{request.url.query}"
        if request.url.query
        else request.url.path
    )
    return HTTPException(
        status.HTTP_303_SEE_OTHER,
        headers={"Location": "/login?" + urlencode({"next": destination})},
    )


async def _user_from_cookie(request: Request, session: AsyncSession) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    query = (
        select(User)
        .join(Session, Session.user_id == User.id)
        .where(
            Session.token_hash == hash_session_token(token),
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(UTC),
        )
    )
    return (await session.scalars(query)).first()


async def _load_shell(request: Request, session: AsyncSession, user: User) -> None:
    """Load the data the app chrome needs (team bar, task list, upcoming) once."""
    rows = (
        await session.execute(
            select(Group, Membership.role)
            .join(Membership, Membership.group_id == Group.id)
            .where(Membership.user_id == user.id)
            .order_by(Group.created_at)
        )
    ).all()
    groups = [
        {
            "id": str(g.id),
            "name": g.name,
            "avatar_key": g.avatar_key,
            "role": role.value,
        }
        for g, role in rows
    ]
    names = {g["id"]: g["name"] for g in groups}
    by_group: dict[str, list[dict]] = {g["id"]: [] for g in groups}
    upcoming: list[dict] = []
    if groups:
        now = datetime.now(UTC)
        found = await session.execute(
            select(
                Assignment.id, Assignment.group_id, Assignment.title, Assignment.due_at
            )
            .where(Assignment.group_id.in_([g.id for g, _ in rows]))
            .order_by(Assignment.created_at)
        )
        for aid, gid, title, due_at in found:
            entry = {"id": str(aid), "title": title}
            by_group[str(gid)].append(entry)
            if due_at is not None:
                aware = due_at if due_at.tzinfo else due_at.replace(tzinfo=UTC)
                if aware >= now:
                    upcoming.append(
                        {**entry, "due_at": aware, "group_name": names[str(gid)]}
                    )
    upcoming.sort(key=lambda item: item["due_at"])
    request.state.user = user
    request.state.shell = {
        "groups": groups,
        "assignments": by_group,
        "upcoming": upcoming[:8],
    }


async def current_user(request: Request, session: DBSession) -> User:
    user = await _user_from_cookie(request, session)
    if not user:
        raise _login_redirect(request)
    await _load_shell(request, session, user)
    return user


async def optional_current_user(request: Request, session: DBSession) -> User | None:
    return await _user_from_cookie(request, session)


CurrentUser = Annotated[User, Depends(current_user)]
OptionalCurrentUser = Annotated[User | None, Depends(optional_current_user)]


def require_teacher(user: CurrentUser) -> User:
    if user.role != UserRole.TEACHER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Teacher access required")
    return user
