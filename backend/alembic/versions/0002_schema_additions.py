"""schema_additions

Revision ID: 0002_schema_additions
Revises: 0001_initial
Create Date: 2026-10-25

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_schema_additions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add security_deposit_amount to student_roster
    op.add_column(
        "student_roster",
        sa.Column(
            "security_deposit_amount",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
    )

    # 2. Create signup_otps table
    op.create_table(
        "signup_otps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("registration_number", sa.String(50), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signup_otps_email", "signup_otps", ["email"])


def downgrade() -> None:
    op.drop_index("ix_signup_otps_email", table_name="signup_otps")
    op.drop_table("signup_otps")
    op.drop_column("student_roster", "security_deposit_amount")
