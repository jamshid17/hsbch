import uuid

from app.calculator import calculate_summary
from app.db import get_db
from app.models import Assignment, Item, Person
from app.models import Session as SessionModel
from app.schemas import SummaryOut
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/sessions", tags=["summary"])


@router.get("/{session_id}/summary", response_model=SummaryOut)
def get_summary(session_id: uuid.UUID, db: Session = Depends(get_db)):
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
    return SummaryOut(currency=session.currency, people=breakdown)
