import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Assignment, Item, Person, Session
from app.schemas import AssignmentsUpdate

router = APIRouter(prefix="/api/sessions", tags=["assignments"])


@router.put("/{session_id}/assignments", status_code=204)
async def update_assignments(
    session_id: uuid.UUID,
    body: AssignmentsUpdate,
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # Fetch valid person IDs for this session (guards against stale IDs from client)
    people_result = await db.execute(select(Person.id).where(Person.session_id == session_id))
    valid_person_ids = {row[0] for row in people_result.all()}

    # Clear existing assignments for this session's items
    items_result = await db.execute(select(Item).where(Item.session_id == session_id))
    item_ids = [i.id for i in items_result.scalars().all()]
    if item_ids:
        existing = await db.execute(
            select(Assignment).where(Assignment.item_id.in_(item_ids))
        )
        for a in existing.scalars().all():
            await db.delete(a)

    for entry in body.assignments:
        for person_id in entry.person_ids:
            if person_id in valid_person_ids:
                db.add(Assignment(item_id=entry.item_id, person_id=person_id))

    session.status = "done"
    await db.commit()
