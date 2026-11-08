"""complete_refund_loop

Revision ID: 0013_complete_refund_loop
Revises: 0012_department_categories
Create Date: 2026-11-08

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0013_complete_refund_loop"
down_revision = "0012_department_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add 'PAYMENT_FAILED' to refund_status enum inside autocommit block for Postgres
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                sa.text("ALTER TYPE refund_status ADD VALUE IF NOT EXISTS 'PAYMENT_FAILED'")
            )

    # 2. Add refund lifecycle columns to refunds table
    op.add_column("refunds", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "refunds",
        sa.Column(
            "verified_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("refunds", sa.Column("accounts_note", sa.String(length=500), nullable=True))
    op.add_column("refunds", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "refunds",
        sa.Column(
            "paid_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("refunds", sa.Column("paid_on", sa.Date(), nullable=True))
    op.add_column("refunds", sa.Column("payment_mode", sa.String(length=20), nullable=True))
    op.add_column("refunds", sa.Column("failure_reason", sa.String(length=500), nullable=True))
    op.add_column("refunds", sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refunds", sa.Column("student_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refunds", sa.Column("student_issue_note", sa.String(length=500), nullable=True))
    op.add_column("refunds", sa.Column("student_issue_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refunds", sa.Column("student_issue_resolved_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_refunds_verified_by_user_id", "refunds", ["verified_by_user_id"])
    op.create_index("ix_refunds_paid_by_user_id", "refunds", ["paid_by_user_id"])

    # 3. Backfill timestamps for existing verified or processed refunds
    bind.execute(
        sa.text(
            """
            UPDATE refunds
            SET verified_at = updated_at
            WHERE status IN ('VERIFIED', 'PROCESSED') AND verified_at IS NULL;
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE refunds
            SET paid_at = updated_at,
                paid_on = updated_at::date
            WHERE status = 'PROCESSED' AND paid_at IS NULL;
            """
        )
    )

    # 4. Check whether any student currently has two or more non-cancelled clearance requests
    dup_check = bind.execute(
        sa.text(
            """
            SELECT roster_id, count(*) as cnt
            FROM clearance_requests
            WHERE status <> 'CANCELLED'
            GROUP BY roster_id
            HAVING count(*) > 1
            """
        )
    ).fetchall()

    if dup_check:
        roster_ids = [str(row[0]) for row in dup_check]
        raise RuntimeError(
            f"Cannot apply migration 0013: found student(s) with multiple non-cancelled clearance requests (roster_ids: {', '.join(roster_ids)}). "
            "Resolve duplicate requests before applying this migration."
        )

    # 5. Update partial unique index on clearance_requests(roster_id)
    op.drop_index("uq_clearance_requests_active_roster", table_name="clearance_requests")
    op.create_index(
        "uq_clearance_requests_active_roster",
        "clearance_requests",
        ["roster_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'CANCELLED'"),
    )


def downgrade() -> None:
    # 1. Revert partial unique index on clearance_requests
    op.drop_index("uq_clearance_requests_active_roster", table_name="clearance_requests")
    op.create_index(
        "uq_clearance_requests_active_roster",
        "clearance_requests",
        ["roster_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('REFUND_VERIFIED', 'CANCELLED')"),
    )

    # 2. Drop indexes and columns from refunds
    op.drop_index("ix_refunds_paid_by_user_id", table_name="refunds")
    op.drop_index("ix_refunds_verified_by_user_id", table_name="refunds")

    op.drop_column("refunds", "student_issue_resolved_at")
    op.drop_column("refunds", "student_issue_at")
    op.drop_column("refunds", "student_issue_note")
    op.drop_column("refunds", "student_confirmed_at")
    op.drop_column("refunds", "failed_at")
    op.drop_column("refunds", "failure_reason")
    op.drop_column("refunds", "payment_mode")
    op.drop_column("refunds", "paid_on")
    op.drop_column("refunds", "paid_by_user_id")
    op.drop_column("refunds", "paid_at")
    op.drop_column("refunds", "accounts_note")
    op.drop_column("refunds", "verified_by_user_id")
    op.drop_column("refunds", "verified_at")
