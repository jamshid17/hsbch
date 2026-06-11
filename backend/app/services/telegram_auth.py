"""Validate Telegram Mini App initData and extract the authenticated user.

See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from urllib.parse import unquote, unquote_plus

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


def _verify_init_data(init_data: str) -> dict:
    """Verify the HMAC of a raw initData string and return its decoded fields.

    Tries every reasonable interpretation and accepts the first that matches
    Telegram's hash, so it is robust to in-transit decoding differences.
    Raises HTTPException(401) if none match.
    """
    received_hash = dict(_split_pairs(init_data)).get("hash")
    if not received_hash:
        raise HTTPException(401, "Missing initData hash")

    attempts: dict[str, str] = {}
    for label, decoded_dict, dcs in _candidates(init_data):
        computed = _hash_of(dcs)
        attempts[label] = computed[:8]
        if hmac.compare_digest(computed, received_hash):
            logger.info("initData matched variant %s", label)
            return decoded_dict

    # TEMPORARY diagnostics (token fingerprint only, plus the user's own
    # initData) to debug remaining signature failures. Remove once resolved.
    debug = {
        "error": "Invalid initData signature",
        "recv": received_hash[:8],
        "attempts": attempts,
        "token_fp": hashlib.sha256(settings.bot_token.encode()).hexdigest()[:10],
        "raw": init_data[:500],
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
