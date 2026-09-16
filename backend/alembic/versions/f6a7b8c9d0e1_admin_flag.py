"""bot_users.is_admin — admin access managed from the panel itself

Until now the only admins were the ids in ADMIN_TELEGRAM_IDS, so adding one
meant editing the server's .env and restarting. This column lets an existing
admin promote/demote anyone from the dashboard; the env ids stay the
un-demotable bootstrap so the panel can never be locked out entirely.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_users",
        sa.Column(
            "is_admin", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("bot_users", "is_admin")
