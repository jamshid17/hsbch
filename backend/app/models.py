import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enum import SourceEnum


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
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    # "collaborative": everyone joins by code and picks their own items.
    # "host_assigns": the host assigns items to everyone themselves.
    assignment_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="collaborative"
    )

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


class BotUser(Base):
    """Top-level, session-independent Telegram identity: tracks the free daily
    receipt-scan quota and any active paid subscription."""

    __tablename__ = "bot_users"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scan_count: Mapped[int] = mapped_column(nullable=False, default=0)
    # Asia/Tashkent calendar date scan_count applies to; reset lazily on read.
    quota_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # UTC instant the subscription lapses; NULL or past = free tier.
    subscription_until: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    # Telegram's own charge id — unique so a retried successful_payment update
    # (at-least-once delivery) can't grant a second subscription period.
    telegram_payment_charge_id: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True
    )
    provider_payment_charge_id: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_tiyin: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
