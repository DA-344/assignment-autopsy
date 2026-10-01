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

import secrets
import string

from sqlalchemy import select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models.group import Group
from ..database.models.membership import Membership
from ..database.models.user import User, UserRole


class InvitesPausedError(Exception):
    """Raised when joining a group whose invite link has been paused by a teacher."""


class GroupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user: User, name: str, description: str) -> Group:
        group = Group(name=name, description=description or None, created_by=user.id)
        self.session.add(group)
        await self.session.flush()
        self.session.add(
            Membership(group_id=group.id, user_id=user.id, role=UserRole.TEACHER)
        )
        await self.session.commit()
        await self.session.refresh(group)
        return group

    async def visible_to(self, user: User) -> list[Group]:
        return list(
            await self.session.scalars(
                select(Group)
                .join(Membership)
                .where(Membership.user_id == user.id)
                .order_by(Group.created_at.desc())
            )
        )

    async def get_member_group(self, group_id, user: User) -> Group | None:
        return await self.session.scalar(
            select(Group)
            .join(Membership)
            .where(Group.id == group_id, Membership.user_id == user.id)
        )

    async def teacher_group(self, group_id, user: User) -> Group | None:
        return await self.session.scalar(
            select(Group)
            .join(Membership)
            .where(
                Group.id == group_id,
                Membership.user_id == user.id,
                Membership.role == UserRole.TEACHER,
            )
        )

    async def member_role(self, group_id, user: User) -> UserRole | None:
        return await self.session.scalar(
            select(Membership.role).where(
                Membership.group_id == group_id, Membership.user_id == user.id
            )
        )

    async def admin_group(self, group_id, user: User) -> Group | None:
        return await self.teacher_group(group_id, user)

    async def update(
        self,
        group: Group,
        *,
        name: str,
        description: str,
        avatar_key: str | None = None,
    ) -> Group:
        group.name, group.description = name.strip(), description.strip() or None
        if avatar_key is not None:
            group.avatar_key = avatar_key
        await self.session.commit()
        return group

    async def generate_invite(self, group: Group, user: User) -> str:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(10):
            code = "".join(secrets.choice(alphabet) for _ in range(10))
            if not await self.session.scalar(
                select(Group.id).where(Group.invite_code == code)
            ):
                group.invite_code = code
                group.invite_uses = 0
                group.invite_created_by = user.id
                group.invites_paused = False
                await self.session.commit()
                return code
        raise RuntimeError("No se pudo generar un código de invitación único")

    async def set_invites_paused(self, group: Group, paused: bool) -> None:
        group.invites_paused = paused
        await self.session.commit()

    async def join_invite(self, code: str, user: User) -> Group | None:
        group = await self.session.scalar(
            select(Group).where(Group.invite_code == code.upper())
        )
        if not group:
            return None
        if group.created_by == user.id:
            return group
        member = await self.session.scalar(
            select(Membership.id).where(
                Membership.group_id == group.id, Membership.user_id == user.id
            )
        )
        if not member:
            if group.invites_paused:
                raise InvitesPausedError()
            self.session.add(
                Membership(group_id=group.id, user_id=user.id, role=UserRole.STUDENT)
            )
            group.invite_uses += 1
            await self.session.commit()
        return group

    async def members(self, group: Group) -> list[User]:
        return list(
            await self.session.scalars(
                select(User)
                .join(Membership)
                .where(Membership.group_id == group.id)
                .order_by(User.last_name, User.first_name)
            )
        )

    async def members_with_roles(
        self, group: Group
    ) -> list[Row[tuple[User, UserRole]]]:
        rows = await self.session.execute(
            select(User, Membership.role)
            .join(Membership)
            .where(Membership.group_id == group.id)
            .order_by(User.last_name, User.first_name)
        )
        return list(rows.all())
