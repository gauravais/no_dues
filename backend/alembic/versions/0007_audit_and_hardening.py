"""audit_and_hardening

Revision ID: 0007_audit_and_hardening
Revises: 0006_lab_courses_and_desc
Create Date: 2026-10-29

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from backend.app.core.crypto import encrypt_bank_account, decrypt_bank_account


# revision identifiers, used by Alembic.
revision = "0007_audit_and_hardening"
down_revision = "0006_lab_courses_and_desc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. clearance_requests: declared_is_hosteller, others_note
    op.add_column(
        "clearance_requests",
        sa.Column(
            "declared_is_hosteller",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "clearance_requests",
        sa.Column("others_note", sa.String(length=1000), nullable=True),
    )

    # 2. department_approvals: added_by_user_id, added_reason
    op.add_column(
        "department_approvals",
        sa.Column("added_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "department_approvals",
        sa.Column("added_reason", sa.String(length=500), nullable=True),
    )
    op.create_foreign_key(
        "fk_dept_approvals_added_by_user",
        "department_approvals",
        "users",
        ["added_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. student_roster: created_by_user_id, source, updated_by_user_id
    op.add_column(
        "student_roster",
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "student_roster",
        sa.Column("source", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "student_roster",
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_roster_created_by_user",
        "student_roster",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_roster_updated_by_user",
        "student_roster",
        "users",
        ["updated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. lab_courses: make academic_department_id nullable
    op.alter_column(
        "lab_courses",
        "academic_department_id",
        nullable=True,
        existing_type=sa.Integer(),
    )

    # 5. request_lab_courses association table
    op.create_table(
        "request_lab_courses",
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("lab_course_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["clearance_requests.id"],
            name="fk_req_lab_courses_request",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lab_course_id"],
            ["lab_courses.id"],
            name="fk_req_lab_courses_course",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("request_id", "lab_course_id"),
    )

    # 6. bank_details: widen account_number to String(255) and encrypt at rest
    op.alter_column(
        "bank_details",
        "account_number",
        type_=sa.String(length=255),
        existing_type=sa.String(length=30),
        nullable=False,
    )

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, account_number FROM bank_details")).fetchall()
    for row_id, acc_num in rows:
        if acc_num and not acc_num.startswith("gAAAAA"):
            enc = encrypt_bank_account(acc_num)
            conn.execute(
                sa.text("UPDATE bank_details SET account_number = :enc WHERE id = :id"),
                {"enc": enc, "id": row_id},
            )


def downgrade() -> None:
    conn = op.get_bind()
    # Decrypt account numbers before shrinking column
    rows = conn.execute(sa.text("SELECT id, account_number FROM bank_details")).fetchall()
    for row_id, acc_num in rows:
        if acc_num and acc_num.startswith("gAAAAA"):
            dec = decrypt_bank_account(acc_num)
            conn.execute(
                sa.text("UPDATE bank_details SET account_number = :dec WHERE id = :id"),
                {"dec": dec[:30], "id": row_id},
            )

    op.alter_column(
        "bank_details",
        "account_number",
        type_=sa.String(length=30),
        existing_type=sa.String(length=255),
        nullable=False,
    )

    op.drop_table("request_lab_courses")

    op.alter_column(
        "lab_courses",
        "academic_department_id",
        nullable=False,
        existing_type=sa.Integer(),
    )

    op.drop_constraint("fk_roster_updated_by_user", "student_roster", type_="foreignkey")
    op.drop_constraint("fk_roster_created_by_user", "student_roster", type_="foreignkey")
    op.drop_column("student_roster", "updated_by_user_id")
    op.drop_column("student_roster", "source")
    op.drop_column("student_roster", "created_by_user_id")

    op.drop_constraint("fk_dept_approvals_added_by_user", "department_approvals", type_="foreignkey")
    op.drop_column("department_approvals", "added_reason")
    op.drop_column("department_approvals", "added_by_user_id")

    op.drop_column("clearance_requests", "others_note")
    op.drop_column("clearance_requests", "declared_is_hosteller")
