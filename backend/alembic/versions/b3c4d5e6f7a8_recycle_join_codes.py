"""join codes are unique among recent sessions, not forever

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2
Create Date: 2026-09-20 12:00:00.000000

A join code is four digits, and every session held one for good. The
ten-thousandth bill would have found no code left to take, and the generator
would have started answering 500 — quietly, and for everyone at once.

Dropping the unique index lets a code go back in the pool once its bill is
old (routers/sessions.py owns the window). `created_at` gets an index because
every code lookup now filters on it.

Downgrade restores the unique index, which fails if codes have been recycled
by then — the data would no longer fit the old rule. Clear the duplicates
first if it ever has to run.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_sessions_code", table_name="sessions")
    op.create_index("ix_sessions_code", "sessions", ["code"], unique=False)
    op.create_index("ix_sessions_created_at", "sessions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_sessions_created_at", table_name="sessions")
    op.drop_index("ix_sessions_code", table_name="sessions")
    op.create_index("ix_sessions_code", "sessions", ["code"], unique=True)
