import uuid

from app.db import get_db
from app.models import Person
from app.models import Session as SessionModel
from app.schemas import PeopleUpdate, PersonOut
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/sessions", tags=["people"])


class AddPersonBody(BaseModel):
    name: str


@router.get("/{session_id}/people", response_model=list[PersonOut])
def list_people(session_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.execute(select(Person).where(Person.session_id == session_id))
        .scalars()
        .all()
    )


@router.post("/{session_id}/people", response_model=PersonOut)
def add_person(
    session_id: uuid.UUID,
    body: AddPersonBody,
    db: Session = Depends(get_db),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    person = Person(session_id=session_id, name=body.name.strip())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


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
