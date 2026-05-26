import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Assignment, Item, Session
from app.schemas import ItemOut, ItemsUpdate

router = APIRouter(prefix="/api/sessions", tags=["items"])


@router.get("/{session_id}/items", response_model=list[ItemOut])
async def list_items(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.session_id == session_id))
    return result.scalars().all()


@router.put("/{session_id}/items", response_model=list[ItemOut])
async def update_items(
    session_id: uuid.UUID,
    body: ItemsUpdate,
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # Delete existing items (cascades assignments)
    existing = await db.execute(select(Item).where(Item.session_id == session_id))
    for item in existing.scalars().all():
        await db.delete(item)

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
    await db.commit()
    for item in new_items:
        await db.refresh(item)
    return new_items
