import uuid

from app.db import get_db
from app.models import Item
from app.models import Session as SessionModel
from app.schemas import ItemOut, ItemsUpdate
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/sessions", tags=["items"])


@router.get("/{session_id}/items", response_model=list[ItemOut])
def list_items(session_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.execute(select(Item).where(Item.session_id == session_id)).scalars().all()


@router.put("/{session_id}/items", response_model=list[ItemOut])
def update_items(
    session_id: uuid.UUID,
    body: ItemsUpdate,
    db: Session = Depends(get_db),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

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
    return new_items
