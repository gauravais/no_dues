"""add user full_name

Revision ID: 0003_add_user_full_name
Revises: 0002_schema_additions
Create Date: 2026-10-26

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_add_user_full_name"
down_revision = "0002_schema_additions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "full_name")
