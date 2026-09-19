"""blocking, and admin permissions that aren't all-or-nothing

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-20 13:00:00.000000

`permissions` defaults to empty, so every existing admin keeps exactly what
being an admin already bought them — the overview — and the owner account is
unaffected either way, since its rights are implicit and never read from here.
The subscription buttons an ordinary admin could use before now need the
`subscriptions` grant; that is the one behaviour this migration changes, and
it changes it towards less.

`blocked_at` null means not blocked, which is every row that exists today.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_users",
        sa.Column(
            "permissions",
            postgresql.ARRAY(sa.String(length=32)),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column("bot_users", sa.Column("blocked_at", sa.DateTime(), nullable=True))
    op.add_column("bot_users", sa.Column("blocked_by", sa.BigInteger(), nullable=True))
    op.add_column(
        "bot_users", sa.Column("block_reason", sa.String(length=200), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("bot_users", "block_reason")
    op.drop_column("bot_users", "blocked_by")
    op.drop_column("bot_users", "blocked_at")
    op.drop_column("bot_users", "permissions")
