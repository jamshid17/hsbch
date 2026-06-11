"""Validate Telegram Mini App initData and extract the authenticated user.

See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from app.config import settings

logger = logging.getLogger("telegram_auth")


@dataclass
class TelegramUser:
    id: int
    first_name: str
    username: str | None = None

    @property
    def display_name(self) -> str:
        return self.first_name or self.username or f"User {self.id}"


def _hmac_hash(pairs: dict) -> str:
    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(
        b"WebAppData", settings.bot_token.encode(), hashlib.sha256
    ).digest()
    return hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()


def _verify_init_data(init_data: str) -> dict:
    """Verify the HMAC of a raw initData string and return its parsed fields.

    Raises HTTPException(401) if the signature is missing or invalid.
    """
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "Missing initData hash")

    # Modern initData also carries an Ed25519 `signature` field for third-party
    # validation. Telegram computes `hash` over the fields excluding both `hash`
    # and `signature`, but older clients omit `signature` entirely. Accept the
    # data if either interpretation matches so we work across client versions.
    without_sig = {k: v for k, v in pairs.items() if k != "signature"}
    candidates = {_hmac_hash(pairs), _hmac_hash(without_sig)}

    if received_hash not in candidates:
        logger.warning(
            "initData signature mismatch: keys=%s received=%s computed=%s",
            sorted(pairs),
            received_hash,
            candidates,
        )
        raise HTTPException(401, "Invalid initData signature")

    return pairs


def _user_from_fields(pairs: dict) -> TelegramUser:
    user_raw = pairs.get("user")
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
