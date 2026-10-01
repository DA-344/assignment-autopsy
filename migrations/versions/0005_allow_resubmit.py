"""Allow students to resubmit an assignment after teacher feedback.

Revision ID: 0005_allow_resubmit
Revises: 0004_assignment_metadata
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_allow_resubmit"
down_revision = "0004_assignment_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("assignments")
    }
    if "allow_resubmit" not in columns:
        op.add_column(
            "assignments",
            sa.Column(
                "allow_resubmit",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.alter_column("assignments", "allow_resubmit", server_default=None)


def downgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("assignments")
    }
    if "allow_resubmit" in columns:
        op.drop_column("assignments", "allow_resubmit")
