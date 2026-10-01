"""Add assignment metadata and username change tracking.

Revision ID: 0004_assignment_metadata_and_username_cooldown
Revises: 0003_user_security_fields
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_assignment_metadata"
down_revision = "0003_user_security_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    assignment_columns = {
        column["name"] for column in inspector.get_columns("assignments")
    }
    user_columns = {column["name"] for column in inspector.get_columns("users")}

    if "return_at" not in assignment_columns:
        op.add_column(
            "assignments",
            sa.Column("return_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "chat_enabled" not in assignment_columns:
        op.add_column(
            "assignments",
            sa.Column(
                "chat_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )
        op.alter_column("assignments", "chat_enabled", server_default=None)
    if "last_username_change_at" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "last_username_change_at", sa.DateTime(timezone=True), nullable=True
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    assignment_columns = {
        column["name"] for column in inspector.get_columns("assignments")
    }
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "chat_enabled" in assignment_columns:
        op.drop_column("assignments", "chat_enabled")
    if "return_at" in assignment_columns:
        op.drop_column("assignments", "return_at")
    if "last_username_change_at" in user_columns:
        op.drop_column("users", "last_username_change_at")
