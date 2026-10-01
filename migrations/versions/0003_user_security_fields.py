"""Add TOTP and OAuth fields to users.

Revision ID: 0003_user_security_fields
Revises: 0002_group_invites
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_user_security_fields"
down_revision = "0002_group_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("users")
    }
    with op.batch_alter_table("users") as batch_op:
        if "username" not in existing_columns:
            batch_op.add_column(
                sa.Column("username", sa.String(length=100), nullable=True)
            )
        if "google_subject" not in existing_columns:
            batch_op.add_column(
                sa.Column("google_subject", sa.String(length=255), nullable=True)
            )
        if "totp_secret_encrypted" not in existing_columns:
            batch_op.add_column(
                sa.Column("totp_secret_encrypted", sa.String(length=255), nullable=True)
            )
        if "recovery_code_hashes" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "recovery_code_hashes",
                    sa.JSON(),
                    nullable=False,
                    server_default="[]",
                )
            )

    op.execute(
        "UPDATE users SET username = LOWER(REPLACE(first_name || '.' || last_name, ' ', '')) WHERE username IS NULL"
    )
    op.execute(
        "UPDATE users SET username = email WHERE username IS NULL OR username = ''"
    )

    constraints = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints("users")
    }
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("username", nullable=False)
        if "uq_users_username" not in constraints:
            batch_op.create_unique_constraint("uq_users_username", ["username"])
        if op.f("ix_users_username") not in indexes:
            batch_op.create_index(op.f("ix_users_username"), ["username"], unique=True)
        batch_op.alter_column("recovery_code_hashes", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index(op.f("ix_users_username"), table_name="users")
        batch_op.drop_constraint("uq_users_username", type_="unique")
        batch_op.drop_column("recovery_code_hashes")
        batch_op.drop_column("totp_secret_encrypted")
        batch_op.drop_column("google_subject")
        batch_op.drop_column("username")
