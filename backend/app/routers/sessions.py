import secrets
import string
import uuid

from app.db import get_db
from app.models import Assignment, Item, Person
from app.models import Session as SessionModel
from app.schemas import (
    MyAssignmentsUpdate,
    ParticipantOut,
    PersonOut,
    PickOut,
    SessionOut,
)
from app.services.telegram_auth import TelegramUser, get_tg_user
from app.ws import manager
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_CODE_ALPHABET = string.digits
_CODE_LEN = 4


def _generate_code(db: Session) -> str:
    """Return a 4-digit numeric code that is not yet used by any session."""
    for _ in range(50):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))
        exists = db.execute(
            select(SessionModel.id).where(SessionModel.code == code)
        ).first()
        if not exists:
            return code
    raise HTTPException(500, "Could not allocate a session code")


def _upsert_person(db: Session, session_id: uuid.UUID, user: TelegramUser) -> Person:
    """Find or create the Person row for this Telegram user in the session."""
    person = db.execute(
        select(Person).where(
            Person.session_id == session_id,
            Person.telegram_user_id == user.id,
        )
    ).scalar_one_or_none()
    if person:
        person.name = user.display_name
        return person
    person = Person(
        session_id=session_id,
        telegram_user_id=user.id,
        name=user.display_name,
    )
    db.add(person)
    db.flush()
    return person


@router.post("", response_model=SessionOut, status_code=201)
def create_session(
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    session = SessionModel(
        code=_generate_code(db),
        telegram_chat_id=user.id,
    )
    db.add(session)
    db.flush()
    # Host is also a participant.
    _upsert_person(db, session.id, user)
    db.commit()
    db.refresh(session)
    return session


@router.get("/by-code/{code}", response_model=SessionOut)
def get_session_by_code(code: str, db: Session = Depends(get_db)):
    row = db.execute(
        select(SessionModel).where(SessionModel.code == code.upper().strip())
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Session not found")
    return row


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    row = db.get(SessionModel, session_id)
    if not row:
        raise HTTPException(404, "Session not found")
    return row


@router.post("/{session_id}/join", response_model=PersonOut)
def join_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    person = _upsert_person(db, session_id, user)
    db.commit()
    db.refresh(person)
    manager.notify(str(session_id), {"type": "updated", "status": session.status})
    return person


@router.get("/{session_id}/participants", response_model=list[ParticipantOut])
def list_participants(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    people = (
        db.execute(select(Person).where(Person.session_id == session_id))
        .scalars()
        .all()
    )
    person_ids = [p.id for p in people]
    picks_by_person: dict[uuid.UUID, list[PickOut]] = {pid: [] for pid in person_ids}
    if person_ids:
        for a in (
            db.execute(
                select(Assignment).where(Assignment.person_id.in_(person_ids))
            )
            .scalars()
            .all()
        ):
            picks_by_person.setdefault(a.person_id, []).append(
                PickOut(item_id=a.item_id, quantity=a.quantity)
            )

    return [
        ParticipantOut(
            id=p.id,
            name=p.name,
            telegram_user_id=p.telegram_user_id,
            is_host=p.telegram_user_id == session.telegram_chat_id,
            picks=picks_by_person.get(p.id, []),
        )
        for p in people
    ]


@router.put("/{session_id}/my-assignments", response_model=list[PickOut])
def update_my_assignments(
    session_id: uuid.UUID,
    body: MyAssignmentsUpdate,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    person = _upsert_person(db, session_id, user)

    valid_item_ids = set(
        db.execute(
            select(Item.id).where(Item.session_id == session_id)
        ).scalars().all()
    )

    # Replace only this person's assignments.
    for a in (
        db.execute(
            select(Assignment).where(Assignment.person_id == person.id)
        ).scalars().all()
    ):
        db.delete(a)

    saved: list[PickOut] = []
    for pick in body.picks:
        if pick.item_id not in valid_item_ids or pick.quantity <= 0:
            continue
        db.add(
            Assignment(
                item_id=pick.item_id,
                person_id=person.id,
                quantity=pick.quantity,
            )
        )
        saved.append(PickOut(item_id=pick.item_id, quantity=pick.quantity))

    db.commit()
    manager.notify(str(session_id), {"type": "updated", "status": session.status})
    return saved


@router.post("/{session_id}/finalize", response_model=SessionOut)
def finalize_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.telegram_chat_id != user.id:
        raise HTTPException(403, "Only the host can finalize the session")
    session.status = "done"
    db.commit()
    db.refresh(session)
    manager.notify(str(session_id), {"type": "updated", "status": session.status})
    return session
