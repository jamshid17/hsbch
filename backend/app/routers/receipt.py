import logging
import uuid
from datetime import datetime

from app.config import settings
from app.db import get_db
from app.errors import api_error
from app.models import BotUser, Item, ReceiptScan
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

# What the upload endpoint accepts. Narrower than "image/*": HEIC and friends
# are images the vision API can't read, and the Mini App already converts
# everything it can decode to JPEG before uploading.
ALLOWED_UPLOAD_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
}
ALLOWED_UPLOAD_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def _claim_scan_slot(db: Session, telegram_user_id: int) -> bool:
    """Atomically spend one of this user's lifetime free scans.

    Returns True if a scan was claimed (or an active subscription makes the
    quota moot), False once all free scans are used up. The UPDATE's row lock
    is what makes this safe under concurrent requests from the same user —
    there's no separate read-then-write race window.
    """
    # Paid tier switched off — every scan is free and nothing is spent, so
    # turning subscriptions back on later finds the counters where it left
    # them rather than exhausted by months of free use.
    if not settings.subscriptions_enabled:
        return True

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
    if not settings.subscriptions_enabled:
        return
    db.execute(
        update(BotUser)
        .where(BotUser.telegram_user_id == telegram_user_id)
        .values(free_scans_used=func.greatest(BotUser.free_scans_used - 1, 0))
    )
    db.commit()


def _log_scan(db: Session, telegram_user_id: int, session_id: uuid.UUID) -> None:
    """Record the scan for the admin dashboard and bump the lifetime counter.

    Only called once the scan actually succeeded, so the numbers match what
    users got out of the app rather than what they attempted.
    """
    user = db.get(BotUser, telegram_user_id)
    subscribed = bool(
        user and user.subscription_until and user.subscription_until > datetime.utcnow()
    )
    db.add(
        ReceiptScan(
            telegram_user_id=telegram_user_id,
            session_id=session_id,
            was_subscribed=subscribed,
        )
    )
    db.execute(
        update(BotUser)
        .where(BotUser.telegram_user_id == telegram_user_id)
        .values(scans_total=BotUser.scans_total + 1)
    )


def _reject_non_image(file: UploadFile) -> None:
    """Refuse anything that isn't a photo before a single byte is read.

    The picker is restricted to images client-side, but "Choose file" on
    desktop and some Android file managers ignore the accept attribute, and a
    PDF reaching the vision API is a guaranteed failure that the user only
    finds out about after waiting. Content-Type comes from the client and can
    be spoofed, so the extension is checked too — this is a usability guard,
    not a security boundary; scan_receipt() still validates the real format.
    """
    media_type = (file.content_type or "").split(";")[0].strip().lower()
    if media_type and media_type not in ALLOWED_UPLOAD_TYPES:
        raise api_error(
            415,
            "upload.not_an_image",
            "Faqat rasm yuklash mumkin (JPEG, PNG, WEBP). "
            "PDF va boshqa fayllar qo'llab-quvvatlanmaydi.",
        )

    name = (file.filename or "").lower()
    if "." in name and not name.endswith(ALLOWED_UPLOAD_EXTENSIONS):
        raise api_error(
            415,
            "upload.not_an_image",
            "Faqat rasm yuklash mumkin (JPEG, PNG, WEBP). "
            "PDF va boshqa fayllar qo'llab-quvvatlanmaydi.",
        )


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

    _reject_non_image(file)

    image_bytes = await file.read()
    if not image_bytes:
        raise api_error(400, "upload.empty", "Bo'sh fayl yuborildi.")
    if len(image_bytes) > settings.max_upload_bytes:
        size_mb = len(image_bytes) / 1024 / 1024
        raise api_error(
            413,
            "upload.too_large",
            f"Rasm juda katta ({size_mb:.1f} MB). "
            f"Eng ko'pi {settings.max_upload_mb} MB.",
            mb=f"{size_mb:.1f}",
            max=settings.max_upload_mb,
        )

    if not _claim_scan_slot(db, tg_user.id):
        raise api_error(
            402,
            "quota.exhausted",
            f"Bepul {settings.free_total_scans} ta skan tugadi. "
            f"Davom etish uchun {settings.subscription_days} kunlik obuna kerak.",
            free=settings.free_total_scans,
            days=settings.subscription_days,
        )

    try:
        result = await scan_receipt(image_bytes, file.content_type or "image/jpeg")
    except ReceiptScanError as e:
        # Expected, user-facing failure (bad format, AI error, unparseable reply)
        _release_scan_slot(db, tg_user.id)
        raise api_error(422, e.code, str(e), **e.params)
    except Exception as e:  # noqa: BLE001 - surface the real cause to the client
        logger.exception("Unexpected error while scanning receipt")
        _release_scan_slot(db, tg_user.id)
        raise api_error(500, "scan.unexpected", f"Kutilmagan xato: {e}")

    _log_scan(db, tg_user.id, session_id)

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
