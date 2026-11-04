"""pilot_readiness

Revision ID: 0009_pilot_readiness
Revises: 0008_refund_payment_reference
Create Date: 2026-10-31

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0009_pilot_readiness"
down_revision = "0008_refund_payment_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add CANCELLED to clearance_status enum
    with op.get_context().autocommit_block():
        op.execute(sa.text("ALTER TYPE clearance_status ADD VALUE IF NOT EXISTS 'CANCELLED'"))

    # 2. Update partial unique index on clearance_requests
    op.drop_index("uq_clearance_requests_active_roster", table_name="clearance_requests")
    op.create_index(
        "uq_clearance_requests_active_roster",
        "clearance_requests",
        ["roster_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('REFUND_VERIFIED', 'CANCELLED')"),
    )

    # 3. Add must_change_password to users
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 4. Create email_outbox table
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("to_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("related_request_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["related_request_id"],
            ["clearance_requests.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_email_outbox_status", "email_outbox", ["status"])
    op.create_index("ix_email_outbox_created_at", "email_outbox", ["created_at"])
    op.create_index("ix_email_outbox_to_email", "email_outbox", ["to_email"])

    # 5. Create auth_rate_limits table
    op.create_table(
        "auth_rate_limits",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_auth_rate_limits_key", "auth_rate_limits", ["key"], unique=True)
    op.create_index("ix_auth_rate_limits_reset_at", "auth_rate_limits", ["reset_at"])


def downgrade() -> None:
    op.drop_table("auth_rate_limits")
    op.drop_table("email_outbox")
    op.drop_column("users", "must_change_password")
    op.drop_index("uq_clearance_requests_active_roster", table_name="clearance_requests")
    op.create_index(
        "uq_clearance_requests_active_roster",
        "clearance_requests",
        ["roster_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'REFUND_VERIFIED'"),
    )
