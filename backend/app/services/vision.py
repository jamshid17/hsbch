import base64
import json

import anthropic
from app.config import settings
from app.schemas import ScanResult
from app.services.prompt import VISIION_PROMPT

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def scan_receipt(image_bytes: bytes, media_type: str) -> ScanResult:
    encoded = base64.standard_b64encode(image_bytes).decode()

    message = await anthropic_client.messages.create(
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
                    {"type": "text", "text": VISIION_PROMPT},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    data = json.loads(raw)
    print(data, "data ant")
    return ScanResult(**data)
