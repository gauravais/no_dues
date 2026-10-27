"""workflow hardening: partial unique index on active clearance requests and previous remarks on approvals

Revision ID: 0004_workflow_hardening
Revises: 0003_add_user_full_name
Create Date: 2026-10-27

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_workflow_hardening"
down_revision = "0003_add_user_full_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Partial unique index ensuring at most one active clearance request per student
    op.create_index(
        "uq_clearance_requests_active_roster",
        "clearance_requests",
        ["roster_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'REFUND_VERIFIED'"),
    )

    # 2. Add previous_remarks column to department_approvals
    op.add_column(
        "department_approvals",
        sa.Column("previous_remarks", sa.String(1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("department_approvals", "previous_remarks")
    op.drop_index("uq_clearance_requests_active_roster", table_name="clearance_requests")
