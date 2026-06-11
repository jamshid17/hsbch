"""collaborative sessions: session code, person telegram_user_id, assignment quantity

Adds:
- sessions.code        short unique join code
- people.telegram_user_id + unique(session_id, telegram_user_id)
- assignments.quantity portions claimed by a person

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-11

"""

import secrets
import string
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALPHABET = string.ascii_uppercase + string.digits


def _gen_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(6))


def upgrade() -> None:
    # --- sessions.code ---
    op.add_column("sessions", sa.Column("code", sa.String(length=8), nullable=True))

    # Backfill existing rows with unique codes.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM sessions")).fetchall()
    used: set[str] = set()
    for (sid,) in rows:
        code = _gen_code()
        while code in used:
            code = _gen_code()
        used.add(code)
        conn.execute(
            sa.text("UPDATE sessions SET code = :c WHERE id = :i"),
            {"c": code, "i": sid},
        )

    op.alter_column("sessions", "code", nullable=False)
    op.create_index("ix_sessions_code", "sessions", ["code"], unique=True)

    # --- people.telegram_user_id ---
    op.add_column(
        "people", sa.Column("telegram_user_id", sa.BigInteger(), nullable=True)
    )
    op.create_unique_constraint(
        "uq_people_session_tg_user", "people", ["session_id", "telegram_user_id"]
    )

    # --- assignments.quantity ---
    op.add_column(
        "assignments",
        sa.Column(
            "quantity",
            sa.Numeric(10, 3),
            nullable=False,
            server_default="1",
        ),
    )
    op.alter_column("assignments", "quantity", server_default=None)


def downgrade() -> None:
    op.drop_column("assignments", "quantity")
    op.drop_constraint("uq_people_session_tg_user", "people", type_="unique")
    op.drop_column("people", "telegram_user_id")
    op.drop_index("ix_sessions_code", table_name="sessions")
    op.drop_column("sessions", "code")
