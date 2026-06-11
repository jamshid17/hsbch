import logging
import uuid

from app.db import get_db
from app.models import Item
from app.models import Session as SessionModel
from app.schemas import ScanResult
from app.services.vision import ReceiptScanError, scan_receipt
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["receipt"])


@router.post("/{session_id}/receipt", response_model=ScanResult)
async def upload_receipt(
    session_id: uuid.UUID,
    file: UploadFile,
    db: Session = Depends(get_db),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, "Bo'sh fayl yuborildi.")

    try:
        result = await scan_receipt(image_bytes, file.content_type or "image/jpeg")
    except ReceiptScanError as e:
        # Expected, user-facing failure (bad format, AI error, unparseable reply)
        raise HTTPException(422, str(e))
    except Exception as e:  # noqa: BLE001 - surface the real cause to the client
        logger.exception("Unexpected error while scanning receipt")
        raise HTTPException(500, f"Kutilmagan xato: {e}")

    session.currency = result.currency
    session.tax = result.tax
    session.tip = result.tip
    session.status = "editing"

    for item_data in result.items:
        db.add(
            Item(
                session_id=session_id,
                name=item_data.name,
                price=item_data.price,
                quantity=item_data.quantity,
                unit=item_data.unit,
            )
        )

    db.commit()
    return result
