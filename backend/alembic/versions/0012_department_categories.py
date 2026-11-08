"""department_categories

Revision ID: 0012_department_categories
Revises: 0011_user_departments
Create Date: 2026-11-07

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0012_department_categories"
down_revision = "0011_user_departments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add 'LAB_WORKSHOP' value to department_applicability enum in autocommit block for Postgres
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                sa.text("ALTER TYPE department_applicability ADD VALUE IF NOT EXISTS 'LAB_WORKSHOP'")
            )

    # 2. Add departments.is_active and departments.created_by_user_id
    op.add_column(
        "departments",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "departments",
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_departments_created_by_user_id",
        "departments",
        ["created_by_user_id"],
    )

    # 3. Add programmes.is_active
    op.add_column(
        "programmes",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # 4. Data conversion: convert ASSIGNED_ONLY departments to LAB_WORKSHOP if referenced by lab_courses
    # or if name starts with 'Lab' / 'Workshop' or ends with ' Lab' (case-insensitive), excluding 'Others'
    convert_query = sa.text(
        """
        UPDATE departments
        SET applicability = 'LAB_WORKSHOP'
        WHERE applicability = 'ASSIGNED_ONLY'
          AND LOWER(name) != 'others'
          AND (
            id IN (SELECT DISTINCT lab_department_id FROM lab_courses WHERE lab_department_id IS NOT NULL)
            OR name ILIKE 'Lab%'
            OR name ILIKE 'Workshop%'
            OR name ILIKE '% Lab'
          )
        """
    )
    bind.execute(convert_query)

    # Query and print converted departments
    converted = bind.execute(
        sa.text(
            """
            SELECT id, name, applicability
            FROM departments
            WHERE applicability = 'LAB_WORKSHOP'
            ORDER BY id
            """
        )
    ).fetchall()
    converted_list = [(row[0], row[1]) for row in converted]
    print(f"\n[Migration 0012] Converted {len(converted_list)} departments to LAB_WORKSHOP: {converted_list}\n")


def downgrade() -> None:
    bind = op.get_bind()

    # 1. Revert LAB_WORKSHOP departments to ASSIGNED_ONLY
    bind.execute(
        sa.text(
            """
            UPDATE departments
            SET applicability = 'ASSIGNED_ONLY'
            WHERE applicability = 'LAB_WORKSHOP'
            """
        )
    )

    # 2. Drop programmes.is_active
    op.drop_column("programmes", "is_active")

    # 3. Drop departments.created_by_user_id and departments.is_active
    op.drop_index("ix_departments_created_by_user_id", table_name="departments")
    op.drop_column("departments", "created_by_user_id")
    op.drop_column("departments", "is_active")
