"""Persist rubric level ordering direction.

Revision ID: 0008_rubric_level_order
Revises: 0007_submission_content_hash
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_rubric_level_order"
down_revision = "0007_submission_content_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("rubrics")
    }
    if "levels_descending" not in columns:
        op.add_column(
            "rubrics",
            sa.Column(
                "levels_descending",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.alter_column("rubrics", "levels_descending", server_default=None)


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("rubrics")
    }
    if "levels_descending" in columns:
        op.drop_column("rubrics", "levels_descending")
