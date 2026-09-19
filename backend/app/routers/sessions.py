import secrets
import string
import uuid
from decimal import ROUND_HALF_UP, Decimal

from app.calculator import unclaimed_items
from app.db import get_db
from app.models import Assignment, Item, Person
from app.models import Session as SessionModel
from app.schemas import (
    FinalizeBody,
    HostAssignmentsUpdate,
    MyAssignmentsUpdate,
    ParticipantOut,
    PersonOut,
    PickOut,
    SessionOut,
    SessionUpdate,
)
from app.services.ratelimit import SlidingWindowLimiter
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


# A four-digit code is small enough to enumerate, and every session behind one
# is somebody's restaurant bill. A person joining a bill looks it up once.
_code_lookups = SlidingWindowLimiter(limit=20, window_seconds=60)

# Quantities are stored with three decimals; an even split has to land on that
# grid. The calculator divides a line total by the ratio of claimed quantities,
# so what matters is only that everyone's figure is the same.
_QTY_STEP = Decimal("0.001")


def _require_host(session: SessionModel, user: TelegramUser, action: str) -> None:
    if session.telegram_chat_id != user.id:
        raise HTTPException(403, f"Only the host can {action}")


def _split_unclaimed_evenly(db: Session, session_id: uuid.UUID) -> None:
    """Hand every unclaimed item to everyone in equal parts.

    An item nobody picked is charged to nobody at all (see
    calculator.unclaimed_items), so its price leaves the split. This is the
    host's way out of that: the shared bread gets shared.
    """
    items = (
        db.execute(select(Item).where(Item.session_id == session_id)).scalars().all()
    )
    people = (
        db.execute(select(Person).where(Person.session_id == session_id))
        .scalars()
        .all()
    )
    if not items or not people:
        return

    assignments = (
        db.execute(
            select(Assignment).where(Assignment.item_id.in_([i.id for i in items]))
        )
        .scalars()
        .all()
    )
    unclaimed = {u["item_id"] for u in unclaimed_items(items, assignments)}
    if not unclaimed:
        return

    for item in items:
        if item.id not in unclaimed:
            continue
        share = max(
            (Decimal(str(item.quantity)) / len(people)).quantize(
                _QTY_STEP, ROUND_HALF_UP
            ),
            _QTY_STEP,
        )
        for person in people:
            db.add(Assignment(item_id=item.id, person_id=person.id, quantity=share))


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


@router.patch("/{session_id}", response_model=SessionOut)
def update_session(
    session_id: uuid.UUID,
    body: SessionUpdate,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    _require_host(session, user, "edit this bill")
    if body.title is not None:
        session.title = body.title
    if body.assignment_mode is not None:
        if body.assignment_mode not in ("collaborative", "host_assigns"):
            raise HTTPException(400, "Invalid assignment_mode")
        session.assignment_mode = body.assignment_mode
    db.commit()
    db.refresh(session)
    return session


@router.get("/by-code/{code}", response_model=SessionOut)
def get_session_by_code(
    code: str,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    if not _code_lookups.hit(user.id):
        raise HTTPException(429, "Too many code lookups. Try again in a minute.")
    row = db.execute(
        select(SessionModel).where(SessionModel.code == code.upper().strip())
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Session not found")
    return row


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: TelegramUser = Depends(get_tg_user),
):
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
def list_participants(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: TelegramUser = Depends(get_tg_user),
):
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


@router.put("/{session_id}/host-assignments", response_model=SessionOut)
def update_host_assignments(
    session_id: uuid.UUID,
    body: HostAssignmentsUpdate,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    """Host-only: replace every Assignment in the session in one shot, then
    finalize immediately. Used by the "host assigns for everyone" mode, where
    no one else ever opens the app to pick their own items."""
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    _require_host(session, user, "assign items")

    valid_item_ids = set(
        db.execute(select(Item.id).where(Item.session_id == session_id)).scalars().all()
    )
    valid_person_ids = set(
        db.execute(select(Person.id).where(Person.session_id == session_id)).scalars().all()
    )

    if valid_item_ids:
        for a in (
            db.execute(select(Assignment).where(Assignment.item_id.in_(valid_item_ids)))
            .scalars()
            .all()
        ):
            db.delete(a)

    for entry in body.assignments:
        if entry.item_id not in valid_item_ids or entry.person_id not in valid_person_ids:
            continue
        if entry.quantity <= 0:
            continue
        db.add(
            Assignment(
                item_id=entry.item_id,
                person_id=entry.person_id,
                quantity=entry.quantity,
            )
        )

    if body.split_unclaimed:
        db.flush()
        _split_unclaimed_evenly(db, session_id)

    session.status = "done"
    db.commit()
    db.refresh(session)
    manager.notify(str(session_id), {"type": "updated", "status": session.status})
    return session


@router.post("/{session_id}/finalize", response_model=SessionOut)
def finalize_session(
    session_id: uuid.UUID,
    body: FinalizeBody = FinalizeBody(),
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_tg_user),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    _require_host(session, user, "finalize the session")
    if body.split_unclaimed:
        _split_unclaimed_evenly(db, session_id)
    session.status = "done"
    db.commit()
    db.refresh(session)
    manager.notify(str(session_id), {"type": "updated", "status": session.status})
    return session
