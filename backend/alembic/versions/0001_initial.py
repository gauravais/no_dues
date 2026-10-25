"""initial_schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-25

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enums ---
    department_kind = sa.Enum("academic", "service", name="department_kind")
    department_applicability = sa.Enum(
        "ALWAYS", "HOSTELLER_ONLY", "ASSIGNED_ONLY", "OWN_ACADEMIC",
        name="department_applicability"
    )
    user_role = sa.Enum(
        "student", "dept_officer", "hod", "registrar_accounts", "admin",
        name="user_role"
    )
    clearance_status = sa.Enum(
        "SUBMITTED", "ACTION_NEEDED", "HOD_REVIEW", "CLEARED", "REFUND_VERIFIED",
        name="clearance_status"
    )
    approval_status = sa.Enum("PENDING", "APPROVED", "REJECTED", name="approval_status")
    refund_status = sa.Enum(
        "PENDING_VERIFICATION", "VERIFIED", "PROCESSED", name="refund_status"
    )

    department_kind.create(op.get_bind(), checkfirst=True)
    department_applicability.create(op.get_bind(), checkfirst=True)
    user_role.create(op.get_bind(), checkfirst=True)
    clearance_status.create(op.get_bind(), checkfirst=True)
    approval_status.create(op.get_bind(), checkfirst=True)
    refund_status.create(op.get_bind(), checkfirst=True)

    # --- faculties ---
    op.create_table(
        "faculties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("short_code", sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_faculties_name"),
        sa.UniqueConstraint("short_code", name="uq_faculties_short_code"),
    )

    # --- departments ---
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", postgresql.ENUM("academic", "service", name="department_kind", create_type=False), nullable=False),
        sa.Column("applicability", postgresql.ENUM("ALWAYS", "HOSTELLER_ONLY", "ASSIGNED_ONLY", "OWN_ACADEMIC", name="department_applicability", create_type=False), nullable=False),
        sa.Column("faculty_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_departments_name"),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculties.id"]),
        sa.CheckConstraint(
            "(kind = 'academic' AND faculty_id IS NOT NULL AND applicability = 'OWN_ACADEMIC') OR (kind = 'service' AND faculty_id IS NULL)",
            name="ck_department_kind_faculty_applicability",
        ),
    )
    op.create_index("ix_departments_faculty_id", "departments", ["faculty_id"])

    # --- programmes ---
    op.create_table(
        "programmes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("academic_department_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_programmes_name"),
        sa.ForeignKeyConstraint(["academic_department_id"], ["departments.id"]),
    )
    op.create_index("ix_programmes_department_id", "programmes", ["academic_department_id"])

    # --- student_roster ---
    op.create_table(
        "student_roster",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("registration_number", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("mobile", sa.String(20), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("programme_id", sa.Integer(), nullable=False),
        sa.Column("is_hosteller", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("registration_number", name="uq_roster_reg_number"),
        sa.UniqueConstraint("email", name="uq_roster_email"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"]),
    )
    op.create_index("ix_student_roster_registration_number", "student_roster", ["registration_number"])
    op.create_index("ix_student_roster_programme_id", "student_roster", ["programme_id"])

    # --- roster_assigned_departments ---
    op.create_table(
        "roster_assigned_departments",
        sa.Column("roster_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("roster_id", "department_id"),
        sa.UniqueConstraint("roster_id", "department_id", name="uq_roster_department"),
        sa.ForeignKeyConstraint(["roster_id"], ["student_roster.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", postgresql.ENUM("student", "dept_officer", "hod", "registrar_accounts", "admin", name="user_role", create_type=False), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("roster_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("roster_id", name="uq_users_roster_id"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["roster_id"], ["student_roster.id"]),
        sa.CheckConstraint(
            "role NOT IN ('dept_officer', 'hod') OR department_id IS NOT NULL",
            name="ck_user_dept_officer_hod_requires_dept",
        ),
        sa.CheckConstraint(
            "role != 'student' OR roster_id IS NOT NULL",
            name="ck_user_student_requires_roster",
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_department_id", "users", ["department_id"])
    op.create_index("ix_users_roster_id", "users", ["roster_id"])

    # --- bank_details ---
    op.create_table(
        "bank_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("roster_id", sa.Integer(), nullable=False),
        sa.Column("account_holder_name", sa.String(255), nullable=False),
        sa.Column("account_number", sa.String(30), nullable=False),
        sa.Column("ifsc_code", sa.String(11), nullable=False),
        sa.Column("bank_address", sa.String(500), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("roster_id", name="uq_bank_details_roster_id"),
        sa.ForeignKeyConstraint(["roster_id"], ["student_roster.id"]),
    )

    # --- clearance_requests ---
    op.create_table(
        "clearance_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("roster_id", sa.Integer(), nullable=False),
        sa.Column("status", postgresql.ENUM("SUBMITTED", "ACTION_NEEDED", "HOD_REVIEW", "CLEARED", "REFUND_VERIFIED", name="clearance_status", create_type=False), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hod_user_id", sa.Integer(), nullable=True),
        sa.Column("hod_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hod_remarks", sa.String(1000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["roster_id"], ["student_roster.id"]),
        sa.ForeignKeyConstraint(["hod_user_id"], ["users.id"]),
    )
    op.create_index("ix_clearance_requests_roster_id", "clearance_requests", ["roster_id"])
    op.create_index("ix_clearance_requests_status", "clearance_requests", ["status"])

    # --- department_approvals ---
    op.create_table(
        "department_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("status", postgresql.ENUM("PENDING", "APPROVED", "REJECTED", name="approval_status", create_type=False), nullable=False),
        sa.Column("remarks", sa.String(1000), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resubmission_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "department_id", name="uq_approval_request_department"),
        sa.ForeignKeyConstraint(["request_id"], ["clearance_requests.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.CheckConstraint(
            "status != 'REJECTED' OR (remarks IS NOT NULL AND remarks != '')",
            name="ck_approval_rejected_requires_remarks",
        ),
    )
    op.create_index("ix_department_approvals_request_id", "department_approvals", ["request_id"])
    op.create_index("ix_department_approvals_department_id", "department_approvals", ["department_id"])
    op.create_index("ix_department_approvals_status", "department_approvals", ["status"])

    # --- certificates ---
    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("certificate_code", sa.String(36), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hod_user_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_certificates_request_id"),
        sa.UniqueConstraint("certificate_code", name="uq_certificates_code"),
        sa.ForeignKeyConstraint(["request_id"], ["clearance_requests.id"]),
        sa.ForeignKeyConstraint(["hod_user_id"], ["users.id"]),
    )

    # --- refunds ---
    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("deposit_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("deductions", sa.Numeric(10, 2), nullable=False),
        sa.Column("final_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", postgresql.ENUM("PENDING_VERIFICATION", "VERIFIED", "PROCESSED", name="refund_status", create_type=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_refunds_request_id"),
        sa.ForeignKeyConstraint(["request_id"], ["clearance_requests.id"]),
    )

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("refunds")
    op.drop_table("certificates")
    op.drop_table("department_approvals")
    op.drop_table("clearance_requests")
    op.drop_table("bank_details")
    op.drop_table("users")
    op.drop_table("roster_assigned_departments")
    op.drop_table("student_roster")
    op.drop_table("programmes")
    op.drop_table("departments")
    op.drop_table("faculties")

    # Drop enums
    for enum_name in [
        "refund_status", "approval_status", "clearance_status",
        "user_role", "department_applicability", "department_kind"
    ]:
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
