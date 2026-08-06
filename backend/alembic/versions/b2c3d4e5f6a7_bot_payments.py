"""bot payments: bot_users (quota + subscription), payments

Adds:
- bot_users: telegram_user_id (PK), scan_count, quota_date, subscription_until
- payments: idempotent record of each successful Telegram payment

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bot_users",
        # Autoincrement must be off: this PK is Telegram's own user id, not a
        # generated identity — SQLAlchemy defaults integer PKs to autoincrement
        # otherwise, which would silently attach an unwanted sequence.
        sa.Column(
            "telegram_user_id", sa.BigInteger(), primary_key=True, autoincrement=False
        ),
        sa.Column("scan_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quota_date", sa.Date(), nullable=True),
        sa.Column("subscription_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(), nullable=True),
    )
    op.alter_column("bot_users", "scan_count", server_default=None)

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(length=128), nullable=False),
        sa.Column("provider_payment_charge_id", sa.String(length=128), nullable=False),
        sa.Column("amount_tiyin", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payments_telegram_user_id", "payments", ["telegram_user_id"])
    op.create_unique_constraint(
        "uq_payments_telegram_payment_charge_id",
        "payments",
        ["telegram_payment_charge_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_payments_telegram_user_id", table_name="payments")
    op.drop_table("payments")
    op.drop_table("bot_users")
