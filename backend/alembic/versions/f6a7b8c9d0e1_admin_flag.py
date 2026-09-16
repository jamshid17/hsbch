"""bot_users.is_admin — admin access managed from the panel itself

Until now the only admins were the ids in ADMIN_TELEGRAM_IDS, so adding one
meant editing the server's .env and restarting. This column moves that into
the database, where an existing admin can grant or revoke it from the
dashboard.

The existing env ids are seeded into the table here, so nobody loses access
on deploy and the panel opens showing exactly who was already an admin. From
then on ADMIN_TELEGRAM_IDS is only a bootstrap: the one id that still carries
weight at runtime is the first, the super admin, who is an admin by
configuration and whom no other admin can demote.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-16

"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _seed_admin_ids() -> list[int]:
    """Read ADMIN_TELEGRAM_IDS straight from the environment.

    Deliberately not via app.config: a migration that imports the settings
    object fails the whole deploy if any unrelated required setting is
    missing, and all this needs is one optional string.
    """
    raw = os.environ.get("ADMIN_TELEGRAM_IDS", "")
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def upgrade() -> None:
    op.add_column(
        "bot_users",
        sa.Column(
            "is_admin", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )

    ids = _seed_admin_ids()
    if not ids:
        return

    bind = op.get_bind()
    # Some configured admins have used the app and have a row; others never
    # opened it. Cover both so the panel lists every one of them from the
    # start, rather than silently dropping the ones who never signed in.
    bind.execute(
        sa.text(
            "UPDATE bot_users SET is_admin = true"
            " WHERE telegram_user_id = ANY(:ids)"
        ),
        {"ids": ids},
    )
    bind.execute(
        sa.text(
            "INSERT INTO bot_users (telegram_user_id, free_scans_used,"
            " scans_total, is_admin, created_at)"
            " SELECT unnest(CAST(:ids AS bigint[])), 0, 0, true, now()"
            " ON CONFLICT (telegram_user_id) DO NOTHING"
        ),
        {"ids": ids},
    )


def downgrade() -> None:
    op.drop_column("bot_users", "is_admin")
