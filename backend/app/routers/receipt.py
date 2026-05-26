import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Item, Session
from app.schemas import ScanResult
from app.vision import scan_receipt

router = APIRouter(prefix="/api/sessions", tags=["receipt"])


@router.post("/{session_id}/receipt", response_model=ScanResult)
async def upload_receipt(
    session_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    image_bytes = await file.read()
    result = await scan_receipt(image_bytes, file.content_type or "image/jpeg")

    session.currency = result.currency
    session.tax = result.tax
    session.tip = result.tip
    session.status = "editing"

    for item_data in result.items:
        db.add(Item(
            session_id=session_id,
            name=item_data.name,
            price=item_data.price,
            quantity=item_data.quantity,
            unit=item_data.unit,
        ))

    await db.commit()
    return result
