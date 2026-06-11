"""Validate Telegram Mini App initData and extract the authenticated user.

See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import base64
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from urllib.parse import parse_qsl

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import Header, HTTPException

from app.config import settings

logger = logging.getLogger("telegram_auth")

# Telegram's Ed25519 public keys for third-party initData signature validation.
# https://core.telegram.org/bots/webapps#validating-data-for-third-party-use
_TG_PUBLIC_KEYS = {
    "prod": "e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d",
    "test": "40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec",
}


@dataclass
class TelegramUser:
    id: int
    first_name: str
    username: str | None = None

    @property
    def display_name(self) -> str:
        return self.first_name or self.username or f"User {self.id}"


def _hmac_hash(fields: dict) -> str:
    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret_key = hmac.new(
        b"WebAppData", settings.bot_token.encode(), hashlib.sha256
    ).digest()
    return hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()


def _verify_hash(parsed: dict) -> bool:
    """Validate the HMAC `hash` against our bot token."""
    received = parsed.get("hash")
    if not received:
        return False
    without_hash = {k: v for k, v in parsed.items() if k != "hash"}
    # Telegram includes every field except `hash`; some client versions add a
    # `signature` field — try with and without it.
    without_sig = {k: v for k, v in without_hash.items() if k != "signature"}
    return any(
        hmac.compare_digest(_hmac_hash(fields), received)
        for fields in (without_hash, without_sig)
    )


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verify_signature(parsed: dict) -> bool:
    """Verify the Ed25519 `signature` field with Telegram's public key.

    Token-independent (uses Telegram's global key + the bot id), so it succeeds
    for genuine Telegram data even when the HMAC `hash` can't be matched.
    """
    signature = parsed.get("signature")
    if not signature:
        return False

    bot_id = settings.bot_token.split(":")[0]
    data_check_string = "\n".join(
        f"{k}={v}"
        for k, v in sorted(parsed.items())
        if k not in ("hash", "signature")
    )
    message = f"{bot_id}:WebAppData\n{data_check_string}".encode()

    try:
        sig = _b64url_decode(signature)
    except (ValueError, base64.binascii.Error):
        return False

    for key_hex in _TG_PUBLIC_KEYS.values():
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex)).verify(
                sig, message
            )
            return True
        except InvalidSignature:
            continue
    return False


def _verify_init_data(init_data: str) -> dict:
    """Validate a raw initData string and return its decoded fields.

    Accepts the data if EITHER the HMAC `hash` matches our bot token OR
    Telegram's Ed25519 `signature` verifies. Raises HTTPException(401) otherwise.
    """
    parsed = dict(parse_qsl(init_data))
    if _verify_hash(parsed) or _verify_signature(parsed):
        return parsed
    raise HTTPException(401, "Invalid initData signature")


def _user_from_fields(parsed: dict) -> TelegramUser:
    user_raw = parsed.get("user")
    if not user_raw:
        raise HTTPException(401, "initData has no user")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        raise HTTPException(401, "Malformed initData user")
    if "id" not in user:
        raise HTTPException(401, "initData user has no id")
    return TelegramUser(
        id=int(user["id"]),
        first_name=user.get("first_name", ""),
        username=user.get("username"),
    )


def get_tg_user(
    x_telegram_init_data: str | None = Header(default=None),
    x_telegram_user_id: str | None = Header(default=None),
    x_telegram_user_name: str | None = Header(default=None),
) -> TelegramUser:
    """FastAPI dependency: resolve the authenticated Telegram user.

    Primary path validates the signed initData header. When DEV_ALLOW_UNSAFE is
    on (local/browser testing) and no initData is present, an unsigned
    X-Telegram-User-Id header is accepted instead.
    """
    if x_telegram_init_data:
        return _user_from_fields(_verify_init_data(x_telegram_init_data))

    if settings.dev_allow_unsafe and x_telegram_user_id:
        return TelegramUser(
            id=int(x_telegram_user_id),
            first_name=x_telegram_user_name or f"User {x_telegram_user_id}",
            username=None,
        )

    raise HTTPException(401, "Telegram authentication required")
