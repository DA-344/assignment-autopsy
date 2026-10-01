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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models.session import Session
from ..database.models.user import User
from ..security.passwords import hash_password, verify_password
from ..security.sessions import hash_session_token, new_session_token, session_expiry
from ..security.two_factor import hash_recovery_code


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        avatar_key: str | None = None,
        username: str | None = None,
    ) -> User:
        exists = await self.session.scalar(
            select(User.id).where(User.email == email.lower())
        )
        if exists:
            raise ValueError("El correo ya está registrado")
        base_username = (
            (
                username or f"{first_name.strip()}.{last_name.strip()}"
                if first_name.strip() and last_name.strip()
                else email.strip().split("@", 1)[0]
            )
            .strip()
            .lower()
            .replace(" ", "")
        )
        if (
            not base_username
            or len(base_username) > 30
            or not base_username.replace("_", "").replace("-", "").isalnum()
        ):
            raise ValueError(
                "El nombre de usuario debe tener entre 1 y 30 caracteres alfanuméricos, guiones o guiones bajos"
            )
        candidate = base_username
        suffix = 1
        while await self.session.scalar(
            select(User.id).where(User.username == candidate)
        ):
            suffix += 1
            candidate = f"{base_username}{suffix}"
        user = User(
            username=candidate,
            email=email.strip().lower(),
            password_hash=hash_password(password),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            avatar_key=avatar_key,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def authenticate_password(self, email: str, password: str) -> User | None:
        user = await self.session.scalar(
            select(User).where(User.email == email.lower())
        )
        if (
            not user
            or not user.password_hash
            or not verify_password(user.password_hash, password)
        ):
            return None
        return user

    async def login_user(self, user: User, ttl: int) -> str:
        token = new_session_token()
        self.session.add(
            Session(
                token_hash=hash_session_token(token),
                user_id=user.id,
                expires_at=session_expiry(ttl),
            )
        )
        await self.session.commit()
        return token

    async def use_recovery_code(self, user: User, code: str) -> bool:
        code_hash = hash_recovery_code(code)
        if code_hash not in user.recovery_code_hashes:
            return False
        user.recovery_code_hashes = [
            item for item in user.recovery_code_hashes if item != code_hash
        ]
        await self.session.commit()
        return True

    async def logout(self, token: str | None) -> None:
        if token:
            record = await self.session.scalar(
                select(Session).where(Session.token_hash == hash_session_token(token))
            )
            if record:
                from datetime import UTC, datetime

                record.revoked_at = datetime.now(UTC)
                await self.session.commit()
