import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


# Auth
class AuthUser(BaseModel):
    id: int
    first_name: str
    username: str | None = None


# Session
class SessionCreate(BaseModel):
    telegram_chat_id: Optional[int] = None


class SessionOut(BaseModel):
    id: uuid.UUID
    code: str
    telegram_chat_id: int
    currency: str
    tax: Decimal
    tip: Decimal
    status: str
    title: Optional[str] = None
    assignment_mode: str = "collaborative"

    model_config = {"from_attributes": True}


class SessionBrief(BaseModel):
    """One line of "my bills" — enough to recognise a dinner, not the split."""

    id: uuid.UUID
    code: str
    title: Optional[str] = None
    status: str
    currency: str
    assignment_mode: str
    created_at: datetime
    # What the receipt came to, items plus tax and tip. Not what the reader
    # personally owes: that needs the whole calculation, per session, and a
    # list is not where anyone reads a number that precise.
    total: Decimal
    people_count: int
    is_host: bool


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    assignment_mode: Optional[str] = None


# Items
class ItemIn(BaseModel):
    name: str
    price: Decimal
    quantity: Decimal = Decimal("1")
    unit: str = "pcs"


class ItemOut(ItemIn):
    id: uuid.UUID

    model_config = {"from_attributes": True}


class ItemsUpdate(BaseModel):
    items: list[ItemIn]
    currency: str = ""
    tax: Decimal = Decimal("0")
    tip: Decimal = Decimal("0")


# People / participants
class PersonOut(BaseModel):
    id: uuid.UUID
    name: str
    telegram_user_id: int | None = None

    model_config = {"from_attributes": True}


class PickOut(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal


class ParticipantOut(BaseModel):
    id: uuid.UUID
    name: str
    telegram_user_id: int | None = None
    is_host: bool = False
    picks: list[PickOut] = []


# My selections (per-user assignment submit)
class MyPick(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Decimal("1")


class MyAssignmentsUpdate(BaseModel):
    picks: list[MyPick]


# Host-assigns mode: host manages a named-only people list and assigns
# every item to everyone themselves (no join code needed).
class AddPersonBody(BaseModel):
    name: str


class PersonNameIn(BaseModel):
    name: str


class PeopleBulkUpdate(BaseModel):
    people: list[PersonNameIn]


class HostAssignmentEntry(BaseModel):
    item_id: uuid.UUID
    person_id: uuid.UUID
    quantity: Decimal = Decimal("1")


class HostAssignmentsUpdate(BaseModel):
    assignments: list[HostAssignmentEntry]
    # Hand anything left unassigned to everyone in equal parts instead of
    # letting its cost drop out of the split.
    split_unclaimed: bool = False


class FinalizeBody(BaseModel):
    split_unclaimed: bool = False


# Summary
class PersonSummary(BaseModel):
    person_id: uuid.UUID
    name: str
    items: list[dict]
    subtotal: Decimal
    extras: Decimal
    total: Decimal


class UnclaimedItem(BaseModel):
    item_id: uuid.UUID
    name: str
    amount: Decimal


class SummaryOut(BaseModel):
    title: str = "Receipt"
    currency: str
    people: list[PersonSummary]
    # Items nobody claimed. Their cost is in no one's total, so the totals
    # below add up to less than the receipt — the client warns rather than
    # showing a smaller bill as if it were the whole one.
    unclaimed: list[UnclaimedItem] = []
    unclaimed_total: Decimal = Decimal("0")


# Receipt scan
class ScannedItem(BaseModel):
    name: str
    price: Decimal
    quantity: Decimal = Decimal("1")
    unit: str = "pcs"


class ScanResult(BaseModel):
    title: str = "Receipt"
    currency: str
    tax: Decimal
    tip: Decimal
    items: list[ScannedItem]
