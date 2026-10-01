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
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from ..app.dependencies import CurrentUser, DBSession
from ..database.models.group import Group
from ..database.models.user import User
from ..services.avatars import load_avatar
from ..services.groups import GroupService

router = APIRouter(prefix="/avatars", tags=["avatars"])
HEADERS = {
    "Cache-Control": "private, max-age=86400",
    "X-Content-Type-Options": "nosniff",
}
CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(404) from None


def _media_type(key: str) -> str:
    return CONTENT_TYPES.get(Path(key).suffix.lower(), "application/octet-stream")


@router.get("/user/{user_id}")
async def user_avatar(
    user_id: str, request: Request, user: CurrentUser, session: DBSession
):
    target = await session.get(User, _uuid(user_id))
    key = target.avatar_key if target else None
    data = await load_avatar(request.app.state.storage, key)
    if data is None or key is None:
        raise HTTPException(404)
    return Response(content=data, media_type=_media_type(key), headers=HEADERS)


@router.get("/group/{group_id}")
async def group_avatar(
    group_id: str, request: Request, user: CurrentUser, session: DBSession
):
    gid = _uuid(group_id)
    if not await GroupService(session).get_member_group(gid, user):
        raise HTTPException(404)
    group = await session.get(Group, gid)
    key = group.avatar_key if group else None
    data = await load_avatar(request.app.state.storage, key)
    if data is None or key is None:
        raise HTTPException(404)
    return Response(content=data, media_type=_media_type(key), headers=HEADERS)
