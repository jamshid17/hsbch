import logging
from datetime import datetime

from app.config import settings
from app.db import get_db
from app.models import BotUser
from app.services.admin_auth import is_admin as user_is_admin
from app.services.telegram_auth import TelegramUser, get_tg_user
from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["payments"])


def _touch_user(db: Session, tg_user: TelegramUser) -> BotUser:
    """Upsert the caller's profile on every app open — Telegram is the source
    of truth for names, and the admin dashboard needs something to show
    besides a numeric id."""
    now = datetime.utcnow()
    stmt = (
        pg_insert(BotUser)
        .values(
            telegram_user_id=tg_user.id,
            first_name=tg_user.first_name,
            username=tg_user.username,
            last_seen_at=now,
        )
        .on_conflict_do_update(
            index_elements=[BotUser.telegram_user_id],
            set_={
                "first_name": tg_user.first_name,
                "username": tg_user.username,
                "last_seen_at": now,
            },
        )
    )
    db.execute(stmt)
    db.commit()
    return db.get(BotUser, tg_user.id)


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    tg_user: TelegramUser = Depends(get_tg_user),
):
    """Quota + subscription state for the current user, plus the card details
    the Mini App shows once the free scans run out."""
    user = _touch_user(db, tg_user)
    now = datetime.utcnow()

    subscribed = bool(user.subscription_until and user.subscription_until > now)
    scans_left = max(settings.free_total_scans - user.free_scans_used, 0)

    # Paid tier switched off: nothing is gated, so there's no card block to
    # show and no quota worth reporting. The client keys every paywall
    # affordance off subscriptions_enabled rather than inferring it.
    card = (
        {
            "number": settings.card_number,
            "holder": settings.card_holder,
            "price_uzs": settings.subscription_price_uzs,
            "admin_contact": settings.admin_contact,
        }
        if settings.subscriptions_enabled and settings.card_number
        else None
    )

    return {
        "telegram_user_id": tg_user.id,
        "subscriptions_enabled": settings.subscriptions_enabled,
        "is_subscribed": subscribed,
        "subscription_until": (
            user.subscription_until.isoformat() if subscribed else None
        ),
        "scans_left": settings.free_total_scans if subscribed else scans_left,
        "free_total_scans": settings.free_total_scans,
        "subscription_days": settings.subscription_days,
        "is_admin": user_is_admin(db, tg_user.id),
        "card": card,
    }
