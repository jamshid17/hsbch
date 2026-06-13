from app.schemas import AuthUser
from app.services.telegram_auth import TelegramUser, get_tg_user
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/telegram", response_model=AuthUser)
def auth_telegram(user: TelegramUser = Depends(get_tg_user)) -> AuthUser:
    """Validate the Telegram initData (via the X-Telegram-Init-Data header) and
    return the authenticated user. Raises 401 if the data is missing/invalid."""
    return AuthUser(
        id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
