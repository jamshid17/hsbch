import base64
import json

import anthropic

from app.config import settings
from app.schemas import ScanResult

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

_PROMPT = """You are a receipt parser. Extract all line items from this receipt image.

Return ONLY valid JSON (no markdown, no explanation) in this exact structure:
{
  "currency": "<symbol or code, e.g. $ or USD>",
  "tax": <number or 0>,
  "tip": <number or 0>,
  "items": [
    {
      "name": "<item name>",
      "price": <unit price as number>,
      "quantity": <quantity as number, default 1>,
      "unit": "<pcs|kg|g|l|ml or pcs if unknown>"
    }
  ]
}

Rules:
- price is the price for ONE unit (divide total by quantity if needed)
- Do not include tax or tip as items
- If you cannot determine tax or tip, use 0
- quantity and unit are required; default to quantity=1, unit="pcs"
"""


async def scan_receipt(image_bytes: bytes, media_type: str) -> ScanResult:
    encoded = base64.standard_b64encode(image_bytes).decode()

    message = await _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
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
                    {"type": "text", "text": _PROMPT},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    data = json.loads(raw)
    return ScanResult(**data)
