"""Add content hashes for submission evaluation caching.

Revision ID: 0007_submission_content_hash
Revises: 0006_files_and_drafts
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_submission_content_hash"
down_revision = "0006_files_and_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("submissions")
    }
    if "content_hash" not in columns:
        op.add_column(
            "submissions",
            sa.Column("content_hash", sa.String(length=64), nullable=True),
        )
        op.create_index("ix_submissions_content_hash", "submissions", ["content_hash"])


def downgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("submissions")
    }
    if "content_hash" in columns:
        op.drop_index("ix_submissions_content_hash", table_name="submissions")
        op.drop_column("submissions", "content_hash")
