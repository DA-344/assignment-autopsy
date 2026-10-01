"""Add team avatar and invitation code.

Revision ID: 0002_group_invites
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_group_invites"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("groups")}
    if "avatar_key" not in columns:
        op.add_column(
            "groups", sa.Column("avatar_key", sa.String(length=500), nullable=True)
        )
    if "invite_code" not in columns:
        op.add_column(
            "groups", sa.Column("invite_code", sa.String(length=10), nullable=True)
        )
        op.create_index("ix_groups_invite_code", "groups", ["invite_code"], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("groups")}
    if "invite_code" in columns:
        op.drop_index("ix_groups_invite_code", table_name="groups")
        op.drop_column("groups", "invite_code")
    if "avatar_key" in columns:
        op.drop_column("groups", "avatar_key")
