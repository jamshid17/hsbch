"""Who counts as an admin.

Two sources, deliberately: the ids in ADMIN_TELEGRAM_IDS are *root* admins —
always in, never demotable, and the only thing standing between a fresh
deployment and an unreachable panel. Everyone else is a normal admin stored in
bot_users.is_admin, promoted and demoted from the dashboard with no .env edit
and no restart.
"""

from app.config import settings
from app.db import get_db
from app.models import BotUser
from app.services.telegram_auth import TelegramUser, get_tg_user
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session


def is_root_admin(telegram_user_id: int) -> bool:
    return telegram_user_id in settings.admin_ids


def is_admin(db: Session, telegram_user_id: int) -> bool:
    if is_root_admin(telegram_user_id):
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
