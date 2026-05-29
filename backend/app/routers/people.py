import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Person, Session
from app.schemas import PeopleUpdate, PersonOut

router = APIRouter(prefix="/api/sessions", tags=["people"])


class AddPersonBody(BaseModel):
    name: str


@router.get("/{session_id}/people", response_model=list[PersonOut])
async def list_people(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Person).where(Person.session_id == session_id))
    return result.scalars().all()


@router.post("/{session_id}/people", response_model=PersonOut)
async def add_person(
    session_id: uuid.UUID,
    body: AddPersonBody,
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    person = Person(session_id=session_id, name=body.name.strip())
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return person


@router.put("/{session_id}/people", response_model=list[PersonOut])
async def update_people(
    session_id: uuid.UUID,
    body: PeopleUpdate,
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    existing = await db.execute(select(Person).where(Person.session_id == session_id))
    for person in existing.scalars().all():
        await db.delete(person)

    new_people = [Person(session_id=session_id, name=p.name) for p in body.people]
    db.add_all(new_people)
    await db.commit()
    for person in new_people:
        await db.refresh(person)
    return new_people
