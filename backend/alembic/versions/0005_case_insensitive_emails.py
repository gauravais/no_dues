"""case-insensitive emails on users and student_roster

Revision ID: 0005_case_insensitive_emails
Revises: 0004_workflow_hardening
Create Date: 2026-10-28

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_case_insensitive_emails"
down_revision = "0004_workflow_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Safety check: ensure lowercasing does not create duplicates in users
    user_dups = conn.execute(
        sa.text(
            "SELECT lower(trim(email)), count(*) "
            "FROM users "
            "GROUP BY lower(trim(email)) "
            "HAVING count(*) > 1"
        )
    ).fetchall()
    if user_dups:
        dup_strs = [f"'{row[0]}' ({row[1]} rows)" for row in user_dups]
        raise RuntimeError(
            f"Cannot apply migration: lowercasing users.email would cause duplicates: {', '.join(dup_strs)}"
        )

    # 2. Safety check: ensure lowercasing does not create duplicates in student_roster
    roster_dups = conn.execute(
        sa.text(
            "SELECT lower(trim(email)), count(*) "
            "FROM student_roster "
            "GROUP BY lower(trim(email)) "
            "HAVING count(*) > 1"
        )
    ).fetchall()
    if roster_dups:
        dup_strs = [f"'{row[0]}' ({row[1]} rows)" for row in roster_dups]
        raise RuntimeError(
            f"Cannot apply migration: lowercasing student_roster.email would cause duplicates: {', '.join(dup_strs)}"
        )

    # 3. Normalise all existing email addresses
    op.execute("UPDATE users SET email = lower(trim(email))")
    op.execute("UPDATE student_roster SET email = lower(trim(email))")

    # 4. Create case-insensitive functional unique indexes on lower(email)
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.create_index(
        "uq_roster_email_lower",
        "student_roster",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_roster_email_lower", table_name="student_roster")
    op.drop_index("uq_users_email_lower", table_name="users")
