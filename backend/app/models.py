import uuid

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    # Short human-friendly code others type to join this session.
    code: Mapped[str] = mapped_column(
        String(8), nullable=False, unique=True, index=True
    )
    # Telegram user id of the host who created the session.
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    tax: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tip: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scanning")

    items: Mapped[list["Item"]] = relationship(
        "Item", back_populates="session", cascade="all, delete-orphan"
    )
    people: Mapped[list["Person"]] = relationship(
        "Person", back_populates="session", cascade="all, delete-orphan"
    )


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=1)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs")

    session: Mapped["Session"] = relationship("Session", back_populates="items")
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="item", cascade="all, delete-orphan"
    )


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "telegram_user_id", name="uq_people_session_tg_user"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE")
    )
    # Telegram user id of this participant (null for legacy manually-added people).
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped["Session"] = relationship("Session", back_populates="people")
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="person", cascade="all, delete-orphan"
    )


class Assignment(Base):
    __tablename__ = "assignments"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # How many units/portions of the item this person claims.
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=1)

    item: Mapped["Item"] = relationship("Item", back_populates="assignments")
    person: Mapped["Person"] = relationship("Person", back_populates="assignments")
