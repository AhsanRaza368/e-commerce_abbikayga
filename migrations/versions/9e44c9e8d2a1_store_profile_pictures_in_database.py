"""store customer profile pictures in database

Revision ID: 9e44c9e8d2a1
Revises: 84c23b9af5d1
Create Date: 2026-11-06 17:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9e44c9e8d2a1"
down_revision: Union[str, Sequence[str], None] = "84c23b9af5d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("profile_picture_data", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "profile_picture_data")
