"""add customer profile picture

Revision ID: 84c23b9af5d1
Revises: 23c1dfc3fbb2
Create Date: 2026-11-05 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "84c23b9af5d1"
down_revision: Union[str, Sequence[str], None] = "23c1dfc3fbb2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("profile_picture_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "profile_picture_url")
