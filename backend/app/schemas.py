import uuid
from decimal import Decimal
from typing import Optional

from app.enum import SourceEnum
from pydantic import BaseModel


# Session
class SessionCreate(BaseModel):
    telegram_chat_id: Optional[int] = None


class SessionOut(BaseModel):
    id: uuid.UUID
    telegram_chat_id: Optional[int]
    source: SourceEnum
    currency: str
    tax: Decimal
    tip: Decimal
    status: str
    title: Optional[str] = None

    model_config = {"from_attributes": True}


class SessionUpdate(BaseModel):
    title: Optional[str] = None


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


# People
class PersonIn(BaseModel):
    name: str


class PersonOut(PersonIn):
    id: uuid.UUID

    model_config = {"from_attributes": True}


class PeopleUpdate(BaseModel):
    people: list[PersonIn]


# Assignments
class AssignmentIn(BaseModel):
    item_id: uuid.UUID
    person_ids: list[uuid.UUID]


class AssignmentsUpdate(BaseModel):
    assignments: list[AssignmentIn]


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
