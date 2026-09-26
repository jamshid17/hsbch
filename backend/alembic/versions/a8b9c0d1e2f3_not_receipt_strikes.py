"""bot_users.not_receipt_strikes — count photos that weren't a receipt

Revision ID: a8b9c0d1e2f3
Revises: d5e6f7a8b9c0
Create Date: 2026-09-26

A scan the model calls "not a receipt" gives the free scan back, so the
quota never stops someone feeding the vision API selfies. This counts them;
the third one blocks the account. Everyone starts at zero.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_users",
        sa.Column(
            "not_receipt_strikes", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("bot_users", "not_receipt_strikes")
