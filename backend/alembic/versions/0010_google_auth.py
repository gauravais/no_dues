"""google_auth

Revision ID: 0010_google_auth
Revises: 0009_pilot_readiness
Create Date: 2026-11-03

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0010_google_auth"
down_revision = "0009_pilot_readiness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Make password_hash nullable for Google-only users
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)

    # 2. Add google_sub (unique identifier from Google)
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])
    op.create_index("ix_users_google_sub", "users", ["google_sub"])

    # 3. Add last_login_at timestamp
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # 1. Drop last_login_at
    op.drop_column("users", "last_login_at")

    # 2. Drop google_sub index and constraint, then column
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "google_sub")

    # 3. Ensure no NULL password_hash before making column NOT NULL
    op.execute(sa.text("UPDATE users SET password_hash = '!disabled_google_user' WHERE password_hash IS NULL"))
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
