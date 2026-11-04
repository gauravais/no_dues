"""lab_courses and department description

Revision ID: 0006_lab_courses_and_desc
Revises: 0005_case_insensitive_emails
Create Date: 2026-10-29

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_lab_courses_and_desc"
down_revision = "0005_case_insensitive_emails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add description to departments table
    op.add_column(
        "departments",
        sa.Column("description", sa.String(length=500), nullable=True),
    )

    # 2. Create lab_courses table
    op.create_table(
        "lab_courses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("academic_department_id", sa.Integer(), nullable=False),
        sa.Column("lab_department_id", sa.Integer(), nullable=False),
        sa.Column("specialization", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["academic_department_id"],
            ["departments.id"],
            name="fk_lab_courses_academic_dept",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lab_department_id"],
            ["departments.id"],
            name="fk_lab_courses_lab_dept",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_lab_courses_code"),
    )
    op.create_index("ix_lab_courses_code", "lab_courses", ["code"])
    op.create_index(
        "ix_lab_courses_academic_department_id",
        "lab_courses",
        ["academic_department_id"],
    )
    op.create_index(
        "ix_lab_courses_lab_department_id",
        "lab_courses",
        ["lab_department_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lab_courses_lab_department_id", table_name="lab_courses")
    op.drop_index("ix_lab_courses_academic_department_id", table_name="lab_courses")
    op.drop_index("ix_lab_courses_code", table_name="lab_courses")
    op.drop_table("lab_courses")
    op.drop_column("departments", "description")
