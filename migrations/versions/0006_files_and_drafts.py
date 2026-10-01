"""Add reference files, multi-file submissions, and nullable descriptions.

Revision ID: 0006_files_and_drafts
Revises: 0005_allow_resubmit
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_files_and_drafts"
down_revision = "0005_allow_resubmit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    assignment_columns = {
        column["name"] for column in inspector.get_columns("assignments")
    }
    submission_columns = {
        column["name"] for column in inspector.get_columns("submissions")
    }
    if "description" in assignment_columns:
        op.alter_column("assignments", "description", nullable=True)
    if "storage_key" in submission_columns:
        op.alter_column("submissions", "storage_key", nullable=True, server_default="")
    if "original_filename" in submission_columns:
        op.alter_column(
            "submissions", "original_filename", nullable=True, server_default="Entrega"
        )
    if "size" in submission_columns:
        op.alter_column("submissions", "size", nullable=True, server_default="0")
    if "content_hash" not in submission_columns:
        op.add_column(
            "submissions",
            sa.Column("content_hash", sa.String(length=64), nullable=True),
        )
        op.create_index("ix_submissions_content_hash", "submissions", ["content_hash"])
    op.create_table(
        "file_assets",
        sa.Column(
            "assignment_id",
            sa.UUID(),
            sa.ForeignKey("assignments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "submission_id",
            sa.UUID(),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "downloadable", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("view_once", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "use_for_ai", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("viewed_at", sa.String(length=40), nullable=True),
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_file_assets_assignment_id", "file_assets", ["assignment_id"])
    op.create_index("ix_file_assets_submission_id", "file_assets", ["submission_id"])
    op.create_index("ix_file_assets_sha256", "file_assets", ["sha256"])
    op.create_unique_constraint(
        "uq_file_assets_storage_key", "file_assets", ["storage_key"]
    )


def downgrade() -> None:
    op.drop_table("file_assets")
