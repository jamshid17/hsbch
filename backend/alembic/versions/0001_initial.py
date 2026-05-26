"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default=""),
        sa.Column("tax", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("tip", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="scanning"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(20), nullable=False, server_default="pcs"),
    )

    op.create_table(
        "people",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
    )

    op.create_table(
        "assignments",
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("person_id", UUID(as_uuid=True), sa.ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("assignments")
    op.drop_table("people")
    op.drop_table("items")
    op.drop_table("sessions")
