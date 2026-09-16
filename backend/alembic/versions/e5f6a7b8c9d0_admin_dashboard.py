"""admin dashboard: user profiles, scan history, card-only payments

- bot_users gains first_name/username/last_seen_at (so the dashboard can show
  who someone is) and scans_total (every scan, not just the free ones)
- receipt_scans records one row per successful scan, for per-day charts
- payments: telegram_payment_charge_id becomes nullable (card transfers have
  none) and gains method/granted_by/note

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bot_users", sa.Column("first_name", sa.String(length=128), nullable=True))
    op.add_column("bot_users", sa.Column("username", sa.String(length=64), nullable=True))
    op.add_column("bot_users", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.add_column(
        "bot_users",
        sa.Column("scans_total", sa.Integer(), nullable=False, server_default="0"),
    )
    # Existing users have only ever scanned on the free allowance, so their
    # lifetime total starts equal to what they spent of it.
    op.execute("UPDATE bot_users SET scans_total = free_scans_used")
    op.alter_column("bot_users", "scans_total", server_default=None)

    op.create_table(
        "receipt_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("was_subscribed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_receipt_scans_telegram_user_id", "receipt_scans", ["telegram_user_id"])
    op.create_index("ix_receipt_scans_created_at", "receipt_scans", ["created_at"])

    op.alter_column(
        "payments",
        "telegram_payment_charge_id",
        existing_type=sa.String(128),
        nullable=True,
    )
    op.add_column(
        "payments",
        sa.Column("method", sa.String(length=16), nullable=False, server_default="card"),
    )
    op.alter_column("payments", "method", server_default=None)
    op.add_column("payments", sa.Column("granted_by", sa.BigInteger(), nullable=True))
    op.add_column("payments", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "note")
    op.drop_column("payments", "granted_by")
    op.drop_column("payments", "method")
    op.execute("DELETE FROM payments WHERE telegram_payment_charge_id IS NULL")
    op.alter_column(
        "payments",
        "telegram_payment_charge_id",
        existing_type=sa.String(128),
        nullable=False,
    )

    op.drop_index("ix_receipt_scans_created_at", table_name="receipt_scans")
    op.drop_index("ix_receipt_scans_telegram_user_id", table_name="receipt_scans")
    op.drop_table("receipt_scans")

    op.drop_column("bot_users", "scans_total")
    op.drop_column("bot_users", "last_seen_at")
    op.drop_column("bot_users", "username")
    op.drop_column("bot_users", "first_name")
