"""summary image file_id

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-19 10:00:00.000000

Caches the Telegram file_id of the rendered "who owes what" image, so the
inline share result can resend the very same photo instead of re-uploading it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("summary_image_file_id", sa.String(length=256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "summary_image_file_id")
