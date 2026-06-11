"""Validate Telegram Mini App initData and extract the authenticated user.

See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import base64
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from urllib.parse import parse_qsl, unquote, unquote_plus

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


def _secret_key() -> bytes:
    return hmac.new(
        b"WebAppData", settings.bot_token.encode(), hashlib.sha256
    ).digest()


def _hash_of(data_check_string: str) -> str:
    return hmac.new(
        _secret_key(), data_check_string.encode(), hashlib.sha256
    ).hexdigest()


def _split_pairs(init_data: str) -> list[tuple[str, str]]:
    """Split a query string into (key, raw_value) pairs without decoding."""
    pairs = []
    for part in init_data.split("&"):
        if not part:
            continue
        key, _, value = part.partition("=")
        pairs.append((key, value))
    return pairs


# Different ways a value might need to be interpreted. The correct one depends
# on how many times the initData was URL-decoded before reaching us: normally
# it arrives encoded and Telegram signed the once-decoded values ("plus"), but
# if a proxy decoded it in transit the values are already decoded ("raw").
_DECODERS = {
    "plus": unquote_plus,
    "unquote": unquote,
    "raw": lambda v: v,
}


def _candidates(init_data: str):
    """Yield (label, decoded_dict, data_check_string) for each interpretation.

    Telegram's `hash` is computed over the fields (sorted by key, excluding
    `hash`) joined by '\\n'. Modern clients add an Ed25519 `signature` field;
    some constructions include it in the hash, some don't — try both.
    """
    raw_pairs = _split_pairs(init_data)
    for dname, decode in _DECODERS.items():
        decoded = [(k, decode(v)) for k, v in raw_pairs if k != "hash"]
        for include_sig in (True, False):
            selected = (
                decoded
                if include_sig
                else [(k, v) for k, v in decoded if k != "signature"]
            )
            dcs = "\n".join(
                f"{k}={v}" for k, v in sorted(selected, key=lambda p: p[0])
            )
            label = f"{dname}/{'sig' if include_sig else 'nosig'}"
            yield label, dict(selected), dcs


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verify_signature(init_data: str) -> bool:
    """Verify the Ed25519 `signature` field with Telegram's public key.

    This is token-independent (uses Telegram's global key + the bot id), so it
    succeeds even when the HMAC `hash` can't be matched against our bot token.
    """
    decoded = dict(parse_qsl(init_data))
    signature = decoded.get("signature")
    if not signature:
        return False

    bot_id = settings.bot_token.split(":")[0]
    data_check_string = "\n".join(
        f"{k}={v}"
        for k, v in sorted(decoded.items())
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

    Accepts the data if EITHER the HMAC `hash` matches our bot token (under any
    reasonable decoding) OR Telegram's Ed25519 `signature` verifies. Raises
    HTTPException(401) otherwise.
    """
    received_hash = dict(_split_pairs(init_data)).get("hash")

    attempts: dict[str, str] = {}
    if received_hash:
        for label, decoded_dict, dcs in _candidates(init_data):
            computed = _hash_of(dcs)
            attempts[label] = computed[:8]
            if hmac.compare_digest(computed, received_hash):
                logger.info("initData matched HMAC variant %s", label)
                return decoded_dict

    # Token-independent fallback: Telegram's Ed25519 signature.
    if _verify_signature(init_data):
        logger.info("initData matched Ed25519 signature")
        return dict(parse_qsl(init_data))

    # TEMPORARY diagnostics (token fingerprint only, plus the user's own
    # initData) to debug remaining signature failures. Remove once resolved.
    debug = {
        "error": "Invalid initData signature",
        "recv": (received_hash or "")[:8],
        "attempts": attempts,
        "sig_present": "signature" in dict(_split_pairs(init_data)),
        "bot_id": settings.bot_token.split(":")[0],
        "token_fp": hashlib.sha256(settings.bot_token.encode()).hexdigest()[:10],
        "raw": init_data[:600],
    }
    logger.warning("initData mismatch: %s", debug)
    raise HTTPException(401, debug)


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
