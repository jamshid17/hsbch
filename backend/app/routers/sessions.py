import uuid

from app.db import get_db
from app.models import Session as SessionModel
from app.schemas import SessionCreate, SessionOut
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=201)
def create_session(body: SessionCreate, db: Session = Depends(get_db)):
    session = SessionModel(
        telegram_chat_id=body.telegram_chat_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    row = db.get(SessionModel, session_id)
    if not row:
        raise HTTPException(404, "Session not found")
    return row
