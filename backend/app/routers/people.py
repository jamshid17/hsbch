import uuid
from datetime import datetime, timezone

from app.db import get_db
from app.models import Person
from app.models import Session as SessionModel
from app.schemas import AddPersonBody, PaidIn, PaidOut, PeopleBulkUpdate, PersonOut
from app.services.telegram_auth import TelegramUser, get_tg_user
from app.ws import manager
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/sessions", tags=["people"])


def _require_host(session: SessionModel, user: TelegramUser) -> None:
    if session.telegram_chat_id != user.id:
        raise HTTPException(403, "Only the host can manage people")


@router.get("/{session_id}/people", response_model=list[PersonOut])
def list_people(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: TelegramUser = Depends(get_tg_user),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
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
    user: TelegramUser = Depends(get_tg_user),
):
    """Add one named (no Telegram account) person without touching existing
    assignments — used to add someone mid-assignment in host_assigns mode."""
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    _require_host(session, user)

    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")

    person = Person(session_id=session_id, telegram_user_id=None, name=name)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.put("/{session_id}/people", response_model=list[PersonOut])
def bulk_set_people(
    session_id: uuid.UUID,
    body: PeopleBulkUpdate,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    """Replace the whole named-people list. Only safe before any assignment
    exists (cascade-deletes wipe assignments along with removed people) — used
    by the initial "enter names" step of host_assigns mode."""
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    _require_host(session, user)

    for person in (
        db.execute(select(Person).where(Person.session_id == session_id))
        .scalars()
        .all()
    ):
        db.delete(person)

    new_people = [
        Person(session_id=session_id, telegram_user_id=None, name=p.name.strip())
        for p in body.people
        if p.name.strip()
    ]
    db.add_all(new_people)
    db.commit()
    for person in new_people:
        db.refresh(person)
    return new_people


@router.post("/{session_id}/people/{person_id}/paid", response_model=PaidOut)
def set_paid(
    session_id: uuid.UUID,
    person_id: uuid.UUID,
    body: PaidIn,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    """Mark someone as having settled up, or take the mark back.

    The host collects the money, so they may tick anyone. A guest may tick
    themselves and nobody else — which is the case that makes this worth
    having at all: the host doesn't have to be told, they watch it happen.
    """
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    person = db.get(Person, person_id)
    if not person or person.session_id != session_id:
        raise HTTPException(404, "Person not found")

    is_host = session.telegram_chat_id == user.id
    if not is_host and person.telegram_user_id != user.id:
        raise HTTPException(403, "Only the host can mark someone else as paid")

    person.paid_at = (
        datetime.now(timezone.utc).replace(tzinfo=None) if body.paid else None
    )
    db.commit()
    manager.notify(str(session_id), {"type": "updated", "status": session.status})
    return PaidOut(person_id=person.id, paid=person.paid_at is not None)


@router.delete("/{session_id}/people/{person_id}", status_code=204)
def delete_person(
    session_id: uuid.UUID,
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    _require_host(session, user)

    person = db.get(Person, person_id)
    if not person or person.session_id != session_id:
        raise HTTPException(404, "Person not found")
    db.delete(person)
    db.commit()
