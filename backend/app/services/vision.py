import base64
import json
import logging

import anthropic
from app.config import settings
from app.schemas import ScanResult
from app.services.prompt import VISIION_PROMPT

logger = logging.getLogger(__name__)

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

# Image formats the Anthropic vision API accepts. Phone photos are often HEIC,
# which is NOT accepted and would otherwise surface as an opaque 500.
SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


class ReceiptScanError(Exception):
    """Receipt could not be scanned. The message is safe to show to the user."""


def _extract_json(raw: str) -> str:
    """Pull the JSON object out of the model reply.

    Claude is asked to return raw JSON, but it sometimes wraps it in a
    ```json ... ``` fence or adds a sentence around it. Strip those so
    json.loads() does not blow up.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text[3:]
        if text[:4].lower() == "json":
            text = text[4:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


async def scan_receipt(image_bytes: bytes, media_type: str) -> ScanResult:
    media_type = (media_type or "").lower()
    if media_type == "image/jpg":
        media_type = "image/jpeg"
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise ReceiptScanError(
            f"Rasm formati qo'llab-quvvatlanmaydi: '{media_type or 'nomaʼlum'}'. "
            "Iltimos JPEG yoki PNG rasm yuklang."
        )

    encoded = base64.standard_b64encode(image_bytes).decode()

    try:
        message = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": encoded,
                            },
                        },
                        {"type": "text", "text": VISIION_PROMPT},
                    ],
                }
            ],
        )
    except anthropic.APIStatusError as e:
        logger.exception("Anthropic API error during receipt scan")
        raise ReceiptScanError(
            f"AI xizmati xatosi ({e.status_code}): {e.message}"
        ) from e
    except anthropic.APIConnectionError as e:
        logger.exception("Anthropic connection error during receipt scan")
        raise ReceiptScanError(
            "AI xizmatiga ulanib bo'lmadi. Keyinroq qayta urinib ko'ring."
        ) from e

    if message.stop_reason == "refusal":
        raise ReceiptScanError("AI rasmni qayta ishlashdan bosh tortdi.")

    raw = next((b.text for b in message.content if b.type == "text"), None)
    if not raw:
        logger.error("No text block in Anthropic response: %r", message.content)
        raise ReceiptScanError("AI javobida matn topilmadi.")

    if message.stop_reason == "max_tokens":
        logger.error("Receipt scan truncated (max_tokens). Raw head: %s", raw[:500])
        raise ReceiptScanError("Chek juda uzun — to'liq o'qib bo'lmadi.")

    try:
        data = json.loads(_extract_json(raw))
        return ScanResult(**data)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.exception("Failed to parse scan result. Raw head: %s", raw[:500])
        raise ReceiptScanError(f"AI javobini o'qib bo'lmadi: {e}") from e
