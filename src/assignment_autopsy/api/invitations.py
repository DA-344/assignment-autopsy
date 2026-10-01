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

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from ..app.dependencies import DBSession, OptionalCurrentUser
from ..services.groups import GroupService

router = APIRouter(tags=["groups"])


@router.get("/invite/{code}")
async def join_invite(
    code: str, request: Request, user: OptionalCurrentUser, session: DBSession
):
    if not code.isalnum() or len(code) > 10:
        raise HTTPException(404)
    if user is None:
        return RedirectResponse(
            "/login?" + urlencode({"next": request.url.path}), status_code=303
        )
    group = await GroupService(session).join_invite(code, user)
    if not group:
        raise HTTPException(404, "Invitación no válida")
    return RedirectResponse(f"/groups/{group.id}", status_code=303)
