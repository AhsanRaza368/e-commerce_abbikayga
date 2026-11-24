"""add pending account email verifications

Revision ID: 5d9c7712a4b8
Revises: 9e44c9e8d2a1
Create Date: 2026-11-06 18:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5d9c7712a4b8"
down_revision: Union[str, Sequence[str], None] = "9e44c9e8d2a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_account_verifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_type", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("username", sa.String(length=80), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "account_type IN ('customer', 'admin')",
            name="ck_pending_account_verification_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_type",
            "email",
            name="uq_pending_account_verification_type_email",
        ),
    )
    op.create_index(
        "ix_pending_account_verifications_email",
        "pending_account_verifications",
        ["email"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pending_account_verifications_email",
        table_name="pending_account_verifications",
    )
    op.drop_table("pending_account_verifications")
