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

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from ..app.dependencies import CurrentUser, DBSession
from ..config import settings
from ..database.models.session import Session
from ..database.models.user import User, UserRole
from ..database.session import get_session
from ..security.csrf import require_csrf
from ..security.passwords import hash_password, verify_password
from ..security.sessions import hash_session_token
from ..security.two_factor import (
    encrypt_totp,
    hash_recovery_code,
    new_recovery_codes,
    new_totp_secret,
    provisioning_uri,
    verify_totp,
)
from ..services.auth import AuthService
from ..services.avatars import remove_stored, store_avatar
from ..services.qr import qr_svg

MIN_PASSWORD_LENGTH = 12

router = APIRouter(tags=["auth"])


def safe_next(value: str | None) -> str:
    return (
        value
        if value
        and value.startswith("/")
        and not value.startswith("//")
        and not urlparse(value).scheme
        else "/groups"
    )


def page(request: Request, name: str, **context):
    """Render a template.

    The CSRF cookie itself is guaranteed by the global middleware in
    app/factory.py (which also fills request.state.csrf_token before this
    ever runs).
    """
    return request.app.state.templates.TemplateResponse(request, name, context)


def session_response(url: str, token: str) -> RedirectResponse:
    response = RedirectResponse(url, status_code=303)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.session_secure,
        samesite=settings.session_same_site,
        max_age=settings.session_ttl,
        path="/",
    )
    return response


@router.get("/")
async def home(request: Request):
    return RedirectResponse(
        "/groups" if request.cookies.get(settings.session_cookie_name) else "/login"
    )


@router.get("/register")
async def register_form(request: Request, next: str | None = None):
    return page(request, "auth/register.html", next=safe_next(next))


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(),
    first_name: str = Form(),
    last_name: str = Form(),
    password: str = Form(),
    username: str = Form(),
    avatar: UploadFile | None = File(None),
    next: str = Form("/groups"),
    csrf_token: str = Form(),
    session: AsyncSession = Depends(get_session),
):
    require_csrf(request, csrf_token)
    destination = safe_next(next)
    if not first_name.strip() or not last_name.strip():
        return page(
            request,
            "auth/register.html",
            error="Nombre y apellidos son obligatorios",
            next=destination,
        )
    avatar_key = None
    if avatar and avatar.filename:
        try:
            avatar_key = await store_avatar(request.app.state.storage, avatar)
        except ValueError as exc:
            return page(request, "auth/register.html", error=str(exc), next=destination)
    try:
        await AuthService(session).register(
            email, password, first_name, last_name, avatar_key, username or None
        )
    except ValueError as exc:
        await remove_stored(request.app.state.storage, avatar_key)
        return page(request, "auth/register.html", error=str(exc), next=destination)
    return RedirectResponse(
        "/login?" + urlencode({"next": destination}), status_code=303
    )


@router.get("/login")
async def login_form(request: Request, next: str | None = None):
    return page(
        request,
        "auth/login.html",
        next=safe_next(next),
        google_enabled=bool(
            settings.google_oauth_client_id
            and settings.google_oauth_client_secret
            and settings.google_oauth_redirect_uri
        ),
    )


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
    next: str | None = Form(None),
    csrf_token: str = Form(),
    session: AsyncSession = Depends(get_session),
):
    require_csrf(request, csrf_token)
    destination = safe_next(next)
    service = AuthService(session)
    user = await service.authenticate_password(email, password)
    if not user:
        return page(
            request,
            "auth/login.html",
            error="Credenciales incorrectas",
            next=destination,
        )
    if user.totp_secret_encrypted:
        return RedirectResponse(
            "/login/verify?" + urlencode({"email": user.email, "next": destination}),
            status_code=303,
        )
    return session_response(
        destination, await service.login_user(user, settings.session_ttl)
    )


@router.get("/login/verify")
async def verify_form(request: Request, email: str, next: str = "/groups"):
    return page(request, "auth/verify.html", email=email, next=safe_next(next))


@router.post("/login/verify")
async def verify_login(
    request: Request,
    email: str = Form(),
    code: str = Form(),
    next: str | None = Form(None),
    csrf_token: str = Form(),
    session: AsyncSession = Depends(get_session),
):
    require_csrf(request, csrf_token)
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if not user or not user.totp_secret_encrypted:
        raise HTTPException(403)
    service = AuthService(session)
    if not (
        verify_totp(user.totp_secret_encrypted, code, settings.app_secret_key)
        or await service.use_recovery_code(user, code)
    ):
        return page(
            request,
            "auth/verify.html",
            error="Código inválido",
            email=email,
            next=safe_next(next),
        )
    return session_response(
        safe_next(next), await service.login_user(user, settings.session_ttl)
    )


@router.post("/logout")
async def logout(
    request: Request,
    csrf_token: str = Form(),
    session: AsyncSession = Depends(get_session),
):
    require_csrf(request, csrf_token)
    await AuthService(session).logout(request.cookies.get(settings.session_cookie_name))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response


def json_result(ok: bool, status_code: int = 200, **payload) -> JSONResponse:
    return JSONResponse({"ok": ok, **payload}, status_code=status_code)


def avatar_url(user: User) -> str | None:
    return f"/avatars/user/{user.id}?v={user.avatar_key}" if user.avatar_key else None


@router.get("/profile")
async def profile(user: CurrentUser):
    # Account settings are a pop-up over the current page (see base.html).
    return RedirectResponse("/groups#settings/account", status_code=303)


@router.post("/profile/username")
async def update_username(
    request: Request,
    user: CurrentUser,
    session: DBSession,
    username: str = Form(),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    candidate = username.strip().lower()
    if (
        not candidate
        or len(candidate) > 30
        or not candidate.replace("_", "").replace("-", "").isalnum()
    ):
        return json_result(False, 422, error="El nombre de usuario no es válido")
    if candidate == user.username:
        return json_result(True, username=candidate)
    if user.last_username_change_at and datetime.now(
        UTC
    ) < user.last_username_change_at + timedelta(days=14):
        return json_result(
            False, 422, error="Solo puedes cambiar tu nombre de usuario cada 14 días"
        )
    taken = await session.scalar(
        select(User.id).where(User.username == candidate, User.id != user.id)
    )
    if taken:
        return json_result(False, 422, error="Ese nombre de usuario ya está ocupado")
    user.username = candidate
    user.last_username_change_at = datetime.now(UTC)
    await session.commit()
    return json_result(True, username=candidate)


@router.post("/profile/avatar")
async def update_avatar(
    request: Request,
    user: CurrentUser,
    session: DBSession,
    avatar: UploadFile | None = File(None),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    if not avatar or not avatar.filename:
        return json_result(False, 422, error="Selecciona una imagen")
    storage = request.app.state.storage
    try:
        key = await store_avatar(storage, avatar)
    except ValueError as exc:
        return json_result(False, 422, error=str(exc))
    previous, user.avatar_key = user.avatar_key, key
    await session.commit()
    await remove_stored(storage, previous)
    return json_result(True, avatar_url=avatar_url(user))


@router.post("/profile/avatar/remove")
async def remove_avatar(
    request: Request, user: CurrentUser, session: DBSession, csrf_token: str = Form()
):
    require_csrf(request, csrf_token)
    previous, user.avatar_key = user.avatar_key, None
    await session.commit()
    await remove_stored(request.app.state.storage, previous)
    return json_result(True, avatar_url=None)


@router.post("/profile/password")
async def change_password(
    request: Request,
    user: CurrentUser,
    session: DBSession,
    current_password: str = Form(""),
    new_password: str = Form(),
    csrf_token: str = Form(),
):
    require_csrf(request, csrf_token)
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return json_result(
            False, 422, error="La nueva contraseña debe tener al menos 12 caracteres"
        )
    # Accounts created through Google have no password yet: allow setting one.
    if user.password_hash and not verify_password(user.password_hash, current_password):
        return json_result(False, 422, error="La contraseña actual no es correcta")
    user.password_hash = hash_password(new_password)
    # Sign out every other device, keep this one.
    current_hash = hash_session_token(
        request.cookies.get(settings.session_cookie_name, "")
    )
    await session.execute(
        update(Session)
        .where(
            Session.user_id == user.id,
            Session.token_hash != current_hash,
            Session.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    return json_result(True)


@router.post("/profile/totp/enable")
async def enable_totp(
    request: Request, user: CurrentUser, session: DBSession, csrf_token: str = Form()
):
    require_csrf(request, csrf_token)
    if user.totp_secret_encrypted:
        return json_result(
            False, 409, error="La verificación en dos pasos ya está activa"
        )
    secret = new_totp_secret()
    user.totp_secret_encrypted = encrypt_totp(secret, settings.app_secret_key)
    recovery_codes = new_recovery_codes(10)
    user.recovery_code_hashes = [hash_recovery_code(code) for code in recovery_codes]
    await session.commit()
    uri = provisioning_uri(secret, user.email)
    return json_result(
        True, secret=secret, uri=uri, qr_svg=qr_svg(uri), recovery_codes=recovery_codes
    )


@router.get("/auth/google")
async def google_login(request: Request, next: str | None = None):
    if not (
        settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.google_oauth_redirect_uri
    ):
        raise HTTPException(404, "Google OAuth no está configurado")
    destination = safe_next(next)
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": str(settings.google_oauth_redirect_uri),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "consent",
        "state": destination,
    }
    return RedirectResponse(
        "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params),
        status_code=303,
    )


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    if not code:
        raise HTTPException(400, "Falta el código OAuth")
    if not (
        settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.google_oauth_redirect_uri
    ):
        raise HTTPException(400, "OAuth no configurado")

    async with httpx.AsyncClient(timeout=20.0) as oauth_client:
        token_response = await oauth_client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": str(settings.google_oauth_redirect_uri),
                "grant_type": "authorization_code",
            },
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        userinfo_response = await oauth_client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
    if userinfo_response.status_code != 200:
        raise HTTPException(
            401, "No se pudo obtener la información del usuario de Google"
        )
    payload = userinfo_response.json()
    google_subject = payload.get("sub")
    email = (payload.get("email") or "").strip().lower()
    if not google_subject or not email:
        raise HTTPException(400, "La respuesta de Google no incluye email o subject")
    user = await session.scalar(
        select(User).where(User.google_subject == google_subject)
    )
    if user is None:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            base_name = (payload.get("given_name") or "Usuario").strip() or "Usuario"
            base_last_name = (payload.get("family_name") or "").strip() or "Alumno"
            user = User(
                username=email.split("@", 1)[0],
                email=email,
                password_hash=None,
                first_name=base_name,
                last_name=base_last_name,
                google_subject=google_subject,
                role=UserRole.STUDENT,
            )
            session.add(user)
        else:
            user.google_subject = google_subject
    await session.commit()
    await session.refresh(user)
    token = await AuthService(session).login_user(user, settings.session_ttl)
    response = RedirectResponse(state or "/groups", status_code=303)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.session_secure,
        samesite=settings.session_same_site,
        max_age=settings.session_ttl,
        path="/",
    )
    return response
