"""drop unique constraint on sessions.telegram_chat_id

Multiple sessions can share a telegram_chat_id: web users all come in with
chat_id 0, and every scan creates a new session. The unique constraint made
the second session creation fail with an IntegrityError (500).

Revision ID: e1f2a3b4c5d6
Revises: b27b3ba8e7b0
Create Date: 2026-06-09

"""

from typing import Sequence, Union

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "b27b3ba8e7b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF EXISTS keeps this idempotent even if the constraint was already
    # dropped manually on the live database.
    op.execute(
        "ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_telegram_chat_id_key"
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "sessions_telegram_chat_id_key", "sessions", ["telegram_chat_id"]
    )
