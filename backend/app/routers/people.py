import uuid

from app.db import get_db
from app.models import Person
from app.models import Session as SessionModel
from app.schemas import PeopleUpdate, PersonOut
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/sessions", tags=["people"])


@router.get("/{session_id}/people", response_model=list[PersonOut])
def list_people(session_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.execute(select(Person).where(Person.session_id == session_id))
        .scalars()
        .all()
    )


@router.put("/{session_id}/people", response_model=list[PersonOut])
def update_people(
    session_id: uuid.UUID,
    body: PeopleUpdate,
    db: Session = Depends(get_db),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    for person in (
        db.execute(select(Person).where(Person.session_id == session_id))
        .scalars()
        .all()
    ):
        db.delete(person)

    new_people = [Person(session_id=session_id, name=p.name) for p in body.people]
    db.add_all(new_people)
    db.commit()
    for person in new_people:
        db.refresh(person)
    return new_people
