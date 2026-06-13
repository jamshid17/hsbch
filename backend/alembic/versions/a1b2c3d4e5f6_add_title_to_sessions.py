"""add title to sessions

Revision ID: a1b2c3d4e5f6
Revises: f726743233da
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f726743233da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sessions', sa.Column('title', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'title')
