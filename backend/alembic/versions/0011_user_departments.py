"""user_departments

Revision ID: 0011_user_departments
Revises: 0010_google_auth
Create Date: 2026-11-06

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0011_user_departments"
down_revision = "0010_google_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create user_departments table
    op.create_table(
        "user_departments",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="RESTRICT"), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_user_departments_department_id", "user_departments", ["department_id"])

    # 2. Idempotent backfill from existing users.department_id
    op.execute(
        sa.text(
            """
            INSERT INTO user_departments (user_id, department_id, created_at)
            SELECT id, department_id, created_at
            FROM users
            WHERE department_id IS NOT NULL
            ON CONFLICT (user_id, department_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_user_departments_department_id", table_name="user_departments")
    op.drop_table("user_departments")
