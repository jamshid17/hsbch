import uuid

from app.db import get_db
from app.models import Item
from app.models import Session as SessionModel
from app.schemas import ItemOut, ItemsUpdate
from app.services.telegram_auth import TelegramUser, get_tg_user
from app.ws import manager
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/sessions", tags=["items"])


@router.get("/{session_id}/items", response_model=list[ItemOut])
def list_items(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: TelegramUser = Depends(get_tg_user),
):
    return db.execute(select(Item).where(Item.session_id == session_id)).scalars().all()


@router.put("/{session_id}/items", response_model=list[ItemOut])
def update_items(
    session_id: uuid.UUID,
    body: ItemsUpdate,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    # This replaces every item in the bill, and deleting an item takes the
    # picks hanging off it with it — only the host gets to do that.
    if session.telegram_chat_id != user.id:
        raise HTTPException(403, "Only the host can edit the items")

    for item in (
        db.execute(select(Item).where(Item.session_id == session_id)).scalars().all()
    ):
        db.delete(item)

    session.currency = body.currency
    session.tax = body.tax
    session.tip = body.tip
    session.status = "assigning"

    new_items = [
        Item(
            session_id=session_id,
            name=i.name,
            price=i.price,
            quantity=i.quantity,
            unit=i.unit,
        )
        for i in body.items
    ]
    db.add_all(new_items)
    db.commit()
    for item in new_items:
        db.refresh(item)
    manager.notify(str(session_id), {"type": "updated", "status": session.status})
    return new_items
