import logging
import uuid
from datetime import datetime

from app.config import settings
from app.db import get_db
from app.models import BotUser, Item
from app.models import Session as SessionModel
from app.schemas import ScanResult
from app.services.telegram_auth import TelegramUser, get_tg_user
from app.services.vision import ReceiptScanError, scan_receipt
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["receipt"])


def _claim_scan_slot(db: Session, telegram_user_id: int) -> bool:
    """Atomically spend one of this user's lifetime free scans.

    Returns True if a scan was claimed (or an active subscription makes the
    quota moot), False once all free scans are used up. The UPDATE's row lock
    is what makes this safe under concurrent requests from the same user —
    there's no separate read-then-write race window.
    """
    now = datetime.utcnow()
    user = db.get(BotUser, telegram_user_id)
    if user and user.subscription_until and user.subscription_until > now:
        return True

    # Ensure a row exists before the conditional UPDATE below can match it.
    db.execute(
        pg_insert(BotUser)
        .values(telegram_user_id=telegram_user_id)
        .on_conflict_do_nothing(index_elements=[BotUser.telegram_user_id])
    )

    stmt = (
        update(BotUser)
        .where(
            BotUser.telegram_user_id == telegram_user_id,
            BotUser.free_scans_used < settings.free_total_scans,
        )
        .values(free_scans_used=BotUser.free_scans_used + 1)
        .returning(BotUser.free_scans_used)
    )
    claimed = db.execute(stmt).first() is not None
    db.commit()
    return claimed


def _release_scan_slot(db: Session, telegram_user_id: int) -> None:
    """Give back a claimed scan when the scan itself fails, so a failed attempt
    doesn't eat one of the user's free scans."""
    db.execute(
        update(BotUser)
        .where(BotUser.telegram_user_id == telegram_user_id)
        .values(free_scans_used=func.greatest(BotUser.free_scans_used - 1, 0))
    )
    db.commit()


@router.post("/{session_id}/receipt", response_model=ScanResult)
async def upload_receipt(
    session_id: uuid.UUID,
    file: UploadFile,
    db: Session = Depends(get_db),
    tg_user: TelegramUser = Depends(get_tg_user),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, "Bo'sh fayl yuborildi.")

    if not _claim_scan_slot(db, tg_user.id):
        raise HTTPException(
            402,
            f"Bepul {settings.free_total_scans} ta skan tugadi. "
            f"{settings.subscription_days} kunlik cheksiz obuna — "
            f"{settings.subscription_stars} ⭐.",
        )

    try:
        result = await scan_receipt(image_bytes, file.content_type or "image/jpeg")
    except ReceiptScanError as e:
        # Expected, user-facing failure (bad format, AI error, unparseable reply)
        _release_scan_slot(db, tg_user.id)
        raise HTTPException(422, str(e))
    except Exception as e:  # noqa: BLE001 - surface the real cause to the client
        logger.exception("Unexpected error while scanning receipt")
        _release_scan_slot(db, tg_user.id)
        raise HTTPException(500, f"Kutilmagan xato: {e}")

    session.currency = result.currency
    session.tax = result.tax
    session.tip = result.tip
    session.status = "editing"
    session.title = result.title

    for item_data in result.items:
        db.add(
            Item(
                session_id=session_id,
                name=item_data.name,
                price=item_data.price,
                quantity=item_data.quantity,
                unit=item_data.unit,
            )
        )

    db.commit()
    return result
