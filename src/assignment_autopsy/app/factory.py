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

import logging
import time

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..api.router import router
from ..config import settings
from ..i18n import request_language, translate, ui_catalog
from ..security.csrf import CSRF_COOKIE, new_csrf_token
from .lifespan import lifespan

_log = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Requests failing validation are not always JSON (most forms here are
    # multipart/urlencoded), so blindly parsing the body as JSON used to raise
    # a second, unhandled exception and mask the real 422 with a bare 500.
    try:
        body_preview = await request.json()
    except Exception:
        try:
            body_preview = dict((await request.form()))
        except Exception:
            body_preview = "<no legible body>"

    _log.error(
        "Validation error detected with body: %s, errors: %s",
        body_preview,
        exc.errors(),
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Assignment Autopsy",
        description="Revisión educativa asistida por IA; la valoración oficial siempre pertenece al profesor.",
        debug=settings.app_debug,
        lifespan=lifespan,
    )
    app.state.settings = settings
    templates = Jinja2Templates(directory="src/assignment_autopsy/templates")
    templates.env.globals["csrf_token"] = lambda request: getattr(
        request.state, "csrf_token", ""
    )
    # Translations come from locales/<lang>/LC_MESSAGES/messages.po
    templates.env.globals["_"] = translate
    templates.env.globals["ui_catalog"] = ui_catalog
    templates.env.globals["ui_language"] = request_language
    # Cache-busts /static/* URLs so a deploy can't leave browsers on stale JS/CSS.
    templates.env.globals["static_version"] = str(int(time.time()))
    app.state.templates = templates
    app.mount(
        "/static", StaticFiles(directory="src/assignment_autopsy/static"), name="static"
    )
    app.include_router(router)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # pyright: ignore[reportArgumentType]

    @app.middleware("http")
    async def ensure_csrf_cookie(request: Request, call_next):
        """Guarantee a CSRF cookie (and matching request.state token) on every request.

        This runs for every route, not just the ones that happen to call a
        helper, so a form can never render with an empty/mismatched token.
        """
        token = request.cookies.get(CSRF_COOKIE)
        needs_cookie = not token
        if needs_cookie:
            token = new_csrf_token()
        request.state.csrf_token = token
        response = await call_next(request)
        if needs_cookie:
            response.set_cookie(
                CSRF_COOKIE,
                token,
                httponly=False,
                secure=settings.session_secure,
                samesite="lax",
                path="/",
            )
        return response

    async def redirect_auth_errors(request, exc: HTTPException):
        if exc.status_code == 303 and exc.headers and exc.headers.get("Location"):
            return RedirectResponse(exc.headers["Location"], status_code=303)
        return JSONResponse(
            {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
        )

    app.add_exception_handler(HTTPException, redirect_auth_errors)  # pyright: ignore[reportArgumentType]
    app.add_route("/favicon.ico", lambda request: RedirectResponse(url="/static/favicon.ico"))
    return app
