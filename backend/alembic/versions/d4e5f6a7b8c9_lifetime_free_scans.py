"""free scans become a lifetime total instead of a daily quota

scan_count was a per-day counter reset against quota_date; it now counts the
free scans a user has spent in total, so the date column is dropped and the
column renamed to match its new meaning. Existing counts carry over as-is
(a user who had scanned twice today starts at 2 of 5).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("bot_users", "scan_count", new_column_name="free_scans_used")
    op.drop_column("bot_users", "quota_date")


def downgrade() -> None:
    op.add_column("bot_users", sa.Column("quota_date", sa.Date(), nullable=True))
    op.alter_column("bot_users", "free_scans_used", new_column_name="scan_count")
