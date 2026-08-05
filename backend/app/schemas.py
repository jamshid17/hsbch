import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.enum import SourceEnum


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


# Summary
class PersonSummary(BaseModel):
    person_id: uuid.UUID
    name: str
    items: list[dict]
    subtotal: Decimal
    extras: Decimal
    total: Decimal


class SummaryOut(BaseModel):
    title: str = "Receipt"
    currency: str
    people: list[PersonSummary]


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
