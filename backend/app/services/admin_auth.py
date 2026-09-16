"""Who counts as an admin.

Admin access lives in bot_users.is_admin and is managed entirely from the
dashboard. The one exception is the super admin — the first id in
ADMIN_TELEGRAM_IDS — who is an admin whether or not the table says so and
whom no other admin can demote. That single fixed point is what guarantees
the panel can never end up with nobody able to open it.

The remaining ids in ADMIN_TELEGRAM_IDS are only a seed: the migration that
introduced the column wrote them into the table, and from then on they are
ordinary admins like anyone promoted from the panel.
"""

from app.config import settings
from app.db import get_db
from app.models import BotUser
from app.services.telegram_auth import TelegramUser, get_tg_user
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session


def is_super_admin(telegram_user_id: int) -> bool:
    return (
        settings.super_admin_id is not None
        and telegram_user_id == settings.super_admin_id
    )


def is_admin(db: Session, telegram_user_id: int) -> bool:
    if is_super_admin(telegram_user_id):
        return True
    user = db.get(BotUser, telegram_user_id)
    return bool(user and user.is_admin)


def require_admin(
    db: Session = Depends(get_db),
    tg_user: TelegramUser = Depends(get_tg_user),
) -> TelegramUser:
    """Every admin endpoint depends on this. 404 rather than 403 so the panel
    doesn't advertise its own existence to non-admins."""
    if not is_admin(db, tg_user.id):
        raise HTTPException(404, "Not found")
    return tg_user
