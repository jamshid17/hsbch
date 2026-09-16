import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    """Top-level, session-independent Telegram identity: tracks the free scan
    allowance, any active subscription, and enough profile data for the admin
    dashboard to show who someone is."""

    __tablename__ = "bot_users"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Refreshed from initData on every Mini App open — Telegram is the source
    # of truth and people do rename themselves.
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Free scans this user has spent in total — never reset; once it reaches
    # settings.free_total_scans only a subscription unlocks further scans.
    free_scans_used: Mapped[int] = mapped_column(nullable=False, default=0)
    # Every successful scan, free or subscribed — what the dashboard counts.
    scans_total: Mapped[int] = mapped_column(nullable=False, default=0)
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
    # Only set for payments Telegram itself settled; card transfers are
    # confirmed by an admin and have no charge id at all.
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True
    )
    provider_payment_charge_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    # "card" (admin-confirmed transfer) or "manual" (comped by an admin).
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="card")
    # Which admin enabled it; NULL for anything granted automatically.
    granted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReceiptScan(Base):
    """One row per successful receipt scan — the raw event the dashboard
    aggregates (per day, per user). bot_users.scans_total is the running
    counter; this is the history."""

    __tablename__ = "receipt_scans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # False when the scan came out of the free allowance.
    was_subscribed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
