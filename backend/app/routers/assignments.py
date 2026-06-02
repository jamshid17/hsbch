import uuid

from app.db import get_db
from app.models import Assignment, Item, Person
from app.models import Session as SessionModel
from app.schemas import AssignmentsUpdate
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/sessions", tags=["assignments"])


@router.put("/{session_id}/assignments", status_code=204)
def update_assignments(
    session_id: uuid.UUID,
    body: AssignmentsUpdate,
    db: Session = Depends(get_db),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    valid_person_ids = set(
        db.execute(select(Person.id).where(Person.session_id == session_id)).scalars().all()
    )

    item_ids = [
        i.id
        for i in db.execute(select(Item).where(Item.session_id == session_id)).scalars().all()
    ]
    if item_ids:
        for a in (
            db.execute(select(Assignment).where(Assignment.item_id.in_(item_ids)))
            .scalars()
            .all()
        ):
            db.delete(a)

    for entry in body.assignments:
        for person_id in entry.person_ids:
            if person_id in valid_person_ids:
                db.add(Assignment(item_id=entry.item_id, person_id=person_id))

    session.status = "done"
    db.commit()
