import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from sqlalchemy import BigInteger, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True
    )
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

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE")
    )
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

    item: Mapped["Item"] = relationship("Item", back_populates="assignments")
    person: Mapped["Person"] = relationship("Person", back_populates="assignments")
