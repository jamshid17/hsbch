import logging
import uuid
from decimal import Decimal

from app.calculator import calculate_summary, unclaimed_items
from app.db import get_db
from app.models import Assignment, Item, Person
from app.models import Session as SessionModel
from app.schemas import SummaryOut, UnclaimedItem
from app.services.telegram_auth import TelegramUser, get_tg_user
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["summary"])

# The share image is rendered by the Mini App itself and posted here; anything
# larger than this is not a receipt card.
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg"}
# Telegram's own cap on a photo caption.
MAX_CAPTION = 1024


# How much of the receipt's name goes into the share query — enough to say
# which bill it is, short enough not to fill the input field.
MAX_QUERY_NAME = 20


def _inline_query(title: str | None, code: str, lang: str) -> str:
    """"<receipt> <code> <lang>" — what the share button types for the user."""
    name = " ".join((title or "").split())
    if len(name) > MAX_QUERY_NAME:
        # Cut back to a word boundary rather than mid-word.
        name = name[:MAX_QUERY_NAME].rsplit(" ", 1)[0]
    return " ".join(p for p in (name, code, lang[:8].strip()) if p)


@router.get("/{session_id}/summary", response_model=SummaryOut)
def get_summary(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: TelegramUser = Depends(get_tg_user),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    items = (
        db.execute(select(Item).where(Item.session_id == session_id)).scalars().all()
    )
    people = (
        db.execute(select(Person).where(Person.session_id == session_id))
        .scalars()
        .all()
    )

    if not people:
        raise HTTPException(400, "No people in session")

    item_ids = [i.id for i in items]
    assignments = (
        db.execute(select(Assignment).where(Assignment.item_id.in_(item_ids)))
        .scalars()
        .all()
        if item_ids
        else []
    )

    breakdown = calculate_summary(session, items, people, assignments)
    paid_ids = {p.id for p in people if p.paid_at is not None}
    owners = {p.id: p.telegram_user_id for p in people}
    for row in breakdown:
        row["paid"] = row["person_id"] in paid_ids
        row["telegram_user_id"] = owners.get(row["person_id"])
    unclaimed = unclaimed_items(items, assignments)
    return SummaryOut(
        title=session.title or "Receipt",
        currency=session.currency,
        people=breakdown,
        unclaimed=[UnclaimedItem(**u) for u in unclaimed],
        unclaimed_total=sum((u["amount"] for u in unclaimed), Decimal("0")),
    )


@router.post("/{session_id}/summary/image", status_code=204)
async def send_summary_image(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    caption: str = Form(default=""),
    share_label: str = Form(default="Ulashish"),
    lang: str = Form(default="uz"),
    db: Session = Depends(get_db),
    tg_user: TelegramUser = Depends(get_tg_user),
):
    """Deliver the split as a picture the user can forward.

    A Mini App can't hand a file to a chat itself, so the card the Mini App
    drew goes to the user's own chat with the bot, carrying a share button.
    Telegram's file_id for that photo is kept on the session so the inline
    share result resends the same upload instead of a text wall.
    """
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    media_type = (file.content_type or "").split(";")[0].strip().lower()
    if media_type and media_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(415, "Faqat PNG yoki JPEG rasm yuborish mumkin.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, "Bo'sh fayl yuborildi.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Rasm juda katta.")

    # Imported here, not at module scope: importing app.bot builds the Bot
    # instance, and the rest of the API must keep starting without a token.
    from aiogram.exceptions import TelegramAPIError
    from aiogram.types import (
        BufferedInputFile,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
    )

    from app.bot import bot

    share_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📤 {share_label[:48]}",
                    # Lands in the user's input field while they pick a
                    # chat, so it reads like "Istanbul 0729 uz": the
                    # receipt, its short join code, and the language (the
                    # bot writes the shared message and can't see the app's
                    # own setting). The bot parses it from the end.
                    switch_inline_query=_inline_query(
                        session.title, session.code, lang
                    ),
                )
            ]
        ]
    )

    try:
        message = await bot.send_photo(
            chat_id=tg_user.id,
            photo=BufferedInputFile(image_bytes, filename="hisob.png"),
            caption=caption[:MAX_CAPTION] or None,
            reply_markup=share_button,
        )
    except TelegramAPIError as e:
        # Most often: the user never pressed /start, so the bot may not write
        # to them. 409 tells the Mini App to fall back to saving the image.
        logger.warning("summary image send failed for %s: %s", tg_user.id, e)
        raise HTTPException(409, "Rasmni botga yuborib bo'lmadi.")

    if message.photo:
        session.summary_image_file_id = message.photo[-1].file_id
        db.commit()
