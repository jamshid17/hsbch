import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.calculator import calculate_summary
from app.db import get_db
from app.models import Assignment, Item, Person, Session
from app.schemas import SummaryOut

router = APIRouter(prefix="/api/sessions", tags=["summary"])


@router.get("/{session_id}/summary", response_model=SummaryOut)
async def get_summary(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    items_result = await db.execute(select(Item).where(Item.session_id == session_id))
    items = items_result.scalars().all()

    people_result = await db.execute(select(Person).where(Person.session_id == session_id))
    people = people_result.scalars().all()

    if not people:
        raise HTTPException(400, "No people in session")

    item_ids = [i.id for i in items]
    assignments_result = await db.execute(
        select(Assignment).where(Assignment.item_id.in_(item_ids))
    ) if item_ids else None
    assignments = assignments_result.scalars().all() if assignments_result else []

    breakdown = calculate_summary(session, items, people, assignments)

    return SummaryOut(currency=session.currency, people=breakdown)
