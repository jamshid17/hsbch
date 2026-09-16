"""stars payments: nullable provider charge id, generic amount, refunds

Telegram Stars charges carry no external provider id and are counted in whole
stars rather than a minor unit, so the Paycom-shaped columns are loosened:
- provider_payment_charge_id -> nullable
- amount_tiyin -> amount (meaning is read through `currency`: XTR or UZS)
- refunded_at added for refundStarPayment

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "payments", "provider_payment_charge_id", existing_type=sa.String(128), nullable=True
    )
    op.alter_column("payments", "amount_tiyin", new_column_name="amount")
    op.add_column("payments", sa.Column("refunded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "refunded_at")
    op.alter_column("payments", "amount", new_column_name="amount_tiyin")
    op.execute(
        "UPDATE payments SET provider_payment_charge_id = '' "
        "WHERE provider_payment_charge_id IS NULL"
    )
    op.alter_column(
        "payments", "provider_payment_charge_id", existing_type=sa.String(128), nullable=False
    )
