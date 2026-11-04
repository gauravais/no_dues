"""refund_payment_reference

Revision ID: 0008_refund_payment_reference
Revises: 0007_audit_and_hardening
Create Date: 2026-10-30

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0008_refund_payment_reference"
down_revision = "0007_audit_and_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "refunds",
        sa.Column("payment_reference", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("refunds", "payment_reference")
