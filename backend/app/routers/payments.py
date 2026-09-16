import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.db import get_db
from app.models import BotUser
from app.services.telegram_auth import TelegramUser, get_tg_user
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["payments"])

TASHKENT = ZoneInfo("Asia/Tashkent")


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    tg_user: TelegramUser = Depends(get_tg_user),
):
    """Quota + subscription state for the current user, so the Mini App can
    show what's left and whether the subscribe button is still relevant."""
    now = datetime.utcnow()
    user = db.get(BotUser, tg_user.id)

    subscribed = bool(
        user and user.subscription_until and user.subscription_until > now
    )
    today = datetime.now(TASHKENT).date()
    used = user.scan_count if user and user.quota_date == today else 0
    scans_left = max(settings.free_daily_scans - used, 0)

    return {
        "is_subscribed": subscribed,
        "subscription_until": (
            user.subscription_until.isoformat() if subscribed else None
        ),
        "scans_left": settings.free_daily_scans if subscribed else scans_left,
        "free_daily_scans": settings.free_daily_scans,
        "price_stars": settings.subscription_stars,
        "subscription_days": settings.subscription_days,
    }


@router.post("/payments/invoice-link")
async def create_invoice_link(tg_user: TelegramUser = Depends(get_tg_user)):
    """A Stars invoice link the Mini App opens with WebApp.openInvoice().

    The subscription itself is never granted here — only the bot webhook's
    successful_payment handler does that, so a client can't fake it.
    """
    from app.bot import create_subscription_invoice_link

    try:
        link = await create_subscription_invoice_link(tg_user.id)
    except Exception as e:  # noqa: BLE001 - surface a clean error to the client
        logger.exception("createInvoiceLink failed")
        raise HTTPException(502, "To'lov havolasini yaratib bo'lmadi.") from e

    return {"link": link, "price_stars": settings.subscription_stars}
