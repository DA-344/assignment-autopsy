"""Track invite usage, who created the active link, and allow pausing it.

Revision ID: 0010_group_invite_management
Revises: 0009_file_asset_views
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_group_invite_management"
down_revision = "0009_file_asset_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("groups")
    }
    if "invite_uses" not in columns:
        op.add_column(
            "groups",
            sa.Column(
                "invite_uses", sa.Integer(), nullable=False, server_default="0"
            ),
        )
        op.alter_column("groups", "invite_uses", server_default=None)
    if "invites_paused" not in columns:
        op.add_column(
            "groups",
            sa.Column(
                "invites_paused",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.alter_column("groups", "invites_paused", server_default=None)
    if "invite_created_by" not in columns:
        op.add_column(
            "groups",
            sa.Column(
                "invite_created_by",
                sa.UUID(),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("groups")
    }
    if "invite_created_by" in columns:
        op.drop_column("groups", "invite_created_by")
    if "invites_paused" in columns:
        op.drop_column("groups", "invites_paused")
    if "invite_uses" in columns:
        op.drop_column("groups", "invite_uses")
