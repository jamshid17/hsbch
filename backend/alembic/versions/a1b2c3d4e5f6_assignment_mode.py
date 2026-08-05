"""host-assigns mode: sessions.assignment_mode

Adds sessions.assignment_mode ("collaborative" | "host_assigns"), used to pick
between everyone claiming their own items via a join code, versus the host
assigning items to everyone themselves.

Revision ID: a1b2c3d4e5f6
Revises: 1fc29f4cb798
Create Date: 2026-08-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "1fc29f4cb798"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "assignment_mode",
            sa.String(length=20),
            nullable=False,
            server_default="collaborative",
        ),
    )
    op.alter_column("sessions", "assignment_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("sessions", "assignment_mode")
