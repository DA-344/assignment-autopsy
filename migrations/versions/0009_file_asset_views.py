"""Track view-once reference files per student instead of globally.

Revision ID: 0009_file_asset_views
Revises: 0008_rubric_level_order
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_file_asset_views"
down_revision = "0008_rubric_level_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "file_asset_views" not in inspector.get_table_names():
        op.create_table(
            "file_asset_views",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "file_asset_id",
                sa.UUID(),
                sa.ForeignKey("file_assets.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.UUID(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_file_asset_views_file_asset_id",
            "file_asset_views",
            ["file_asset_id"],
        )
        op.create_index("ix_file_asset_views_user_id", "file_asset_views", ["user_id"])
        op.create_unique_constraint(
            "uq_file_asset_views_file_asset_id",
            "file_asset_views",
            ["file_asset_id", "user_id"],
        )
    columns = {column["name"] for column in inspector.get_columns("file_assets")}
    if "viewed_at" in columns:
        op.drop_column("file_assets", "viewed_at")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("file_assets")}
    if "viewed_at" not in columns:
        op.add_column(
            "file_assets", sa.Column("viewed_at", sa.String(length=40), nullable=True)
        )
    if "file_asset_views" in inspector.get_table_names():
        op.drop_table("file_asset_views")
