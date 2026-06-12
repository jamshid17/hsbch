import httpx
from app.config import settings
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["config"])

# Cache the bot username so we only hit getMe once per process.
_bot_username: str | None = None


@router.get("/config")
def get_config():
    """Public client config — currently just the bot username, used to build
    t.me/<bot>?startapp=<code> deep links for sharing."""
    global _bot_username
    if _bot_username is None:
        try:
            resp = httpx.get(
                f"https://api.telegram.org/bot{settings.bot_token}/getMe",
                timeout=10,
            )
            _bot_username = resp.json().get("result", {}).get("username")
        except Exception:
            _bot_username = None
    return {"bot_username": _bot_username}
