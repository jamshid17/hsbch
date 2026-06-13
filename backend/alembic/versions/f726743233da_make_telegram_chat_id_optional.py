"""make telegram_chat_id optional

Revision ID: f726743233da
Revises: b27b3ba8e7b0
Create Date: 2026-06-02 17:39:50.515022

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f726743233da'
down_revision: Union[str, None] = 'b27b3ba8e7b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

source_enum = sa.Enum('TELEGRAM', 'WEB', name='sourceenum')


def upgrade() -> None:
    source_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('sessions', sa.Column('source', source_enum, nullable=False, server_default='TELEGRAM'))
    op.alter_column('sessions', 'telegram_chat_id',
               existing_type=sa.BIGINT(),
               nullable=True)
    op.drop_constraint('sessions_telegram_chat_id_key', 'sessions', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint('sessions_telegram_chat_id_key', 'sessions', ['telegram_chat_id'])
    op.alter_column('sessions', 'telegram_chat_id',
               existing_type=sa.BIGINT(),
               nullable=False)
    op.drop_column('sessions', 'source')
    source_enum.drop(op.get_bind(), checkfirst=True)
