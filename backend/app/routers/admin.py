import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.db import get_db
from app.models import BotUser, Payment, ReceiptScan
from app.models import Session as SessionModel
from app.services.telegram_auth import TelegramUser, get_tg_user
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Date, case, cast, func, or_, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

TASHKENT = ZoneInfo("Asia/Tashkent")


def require_admin(tg_user: TelegramUser = Depends(get_tg_user)) -> TelegramUser:
    """Every admin endpoint depends on this. 404 rather than 403 so the panel
    doesn't advertise its own existence to non-admins."""
    if tg_user.id not in settings.admin_ids:
        raise HTTPException(404, "Not found")
    return tg_user


def _today() -> date:
    return datetime.now(TASHKENT).date()


def _day_start_utc(days_ago: int = 0) -> datetime:
    """UTC instant that Tashkent's calendar day started, `days_ago` days back —
    stored timestamps are UTC but the business day is local."""
    local_midnight = datetime.combine(
        _today() - timedelta(days=days_ago), datetime.min.time(), tzinfo=TASHKENT
    )
    return local_midnight.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _: TelegramUser = Depends(require_admin),
):
    now = datetime.utcnow()
    today_start = _day_start_utc()
    week_start = _day_start_utc(6)

    def count(model, *where):
        return db.execute(
            select(func.count()).select_from(model).where(*where)
        ).scalar_one()

    users_total = count(BotUser)
    users_today = count(BotUser, BotUser.created_at >= today_start)
    users_week = count(BotUser, BotUser.created_at >= week_start)

    scans_total = count(ReceiptScan)
    scans_today = count(ReceiptScan, ReceiptScan.created_at >= today_start)
    scans_week = count(ReceiptScan, ReceiptScan.created_at >= week_start)

    subscribed = count(
        BotUser,
        BotUser.subscription_until.is_not(None),
        BotUser.subscription_until > now,
    )
    # Free users who can't scan any more — the pool the subscription pitch is
    # actually shown to.
    exhausted = count(
        BotUser,
        BotUser.free_scans_used >= settings.free_total_scans,
        or_(
            BotUser.subscription_until.is_(None),
            BotUser.subscription_until <= now,
        ),
    )

    sessions_total = count(SessionModel)

    month_start = _day_start_utc(_today().day - 1)
    revenue_month = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.created_at >= month_start, Payment.refunded_at.is_(None)
        )
    ).scalar_one()
    payments_month = count(
        Payment, Payment.created_at >= month_start, Payment.refunded_at.is_(None)
    )

    # Daily scans for the last 14 days, zero-filled so the chart has no gaps.
    rows = db.execute(
        select(
            cast(ReceiptScan.created_at, Date).label("day"),
            func.count().label("n"),
        )
        .where(ReceiptScan.created_at >= _day_start_utc(13))
        .group_by("day")
        .order_by("day")
    ).all()
    by_day = {r.day: r.n for r in rows}
    daily = [
        {
            "date": (d := _today() - timedelta(days=i)).isoformat(),
            "scans": by_day.get(d, 0),
        }
        for i in range(13, -1, -1)
    ]

    return {
        "users_total": users_total,
        "users_today": users_today,
        "users_week": users_week,
        "scans_total": scans_total,
        "scans_today": scans_today,
        "scans_week": scans_week,
        "subscribed": subscribed,
        "exhausted": exhausted,
        "sessions_total": sessions_total,
        "revenue_month": int(revenue_month),
        "payments_month": payments_month,
        "price_uzs": settings.subscription_price_uzs,
        "daily_scans": daily,
    }


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _: TelegramUser = Depends(require_admin),
    search: str = "",
    filter: str = Query("all", pattern="^(all|subscribed|exhausted|active)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    now = datetime.utcnow()
    is_subscribed = case(
        (
            BotUser.subscription_until.is_not(None)
            & (BotUser.subscription_until > now),
            True,
        ),
        else_=False,
    )

    stmt = select(BotUser)
    if search:
        term = f"%{search.strip().lstrip('@').lower()}%"
        conditions = [
            func.lower(func.coalesce(BotUser.username, "")).like(term),
            func.lower(func.coalesce(BotUser.first_name, "")).like(term),
        ]
        if search.strip().isdigit():
            conditions.append(BotUser.telegram_user_id == int(search.strip()))
        stmt = stmt.where(or_(*conditions))

    if filter == "subscribed":
        stmt = stmt.where(is_subscribed)
    elif filter == "exhausted":
        stmt = stmt.where(
            ~is_subscribed, BotUser.free_scans_used >= settings.free_total_scans
        )
    elif filter == "active":
        stmt = stmt.where(BotUser.last_seen_at >= _day_start_utc(6))

    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    users = (
        db.execute(
            stmt.order_by(BotUser.last_seen_at.desc().nullslast())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    return {
        "total": total,
        "users": [
            {
                "telegram_user_id": u.telegram_user_id,
                "first_name": u.first_name,
                "username": u.username,
                "free_scans_used": u.free_scans_used,
                "free_total_scans": settings.free_total_scans,
                "scans_total": u.scans_total,
                "is_subscribed": bool(
                    u.subscription_until and u.subscription_until > now
                ),
                "subscription_until": (
                    u.subscription_until.isoformat() if u.subscription_until else None
                ),
                "last_seen_at": u.last_seen_at.isoformat() if u.last_seen_at else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


class GrantIn(BaseModel):
    days: int = Field(default=0, ge=0, le=3650)
    amount_uzs: int | None = Field(default=None, ge=0)
    note: str | None = None


@router.post("/users/{telegram_user_id}/grant")
def grant_subscription(
    telegram_user_id: int,
    body: GrantIn,
    db: Session = Depends(get_db),
    admin: TelegramUser = Depends(require_admin),
):
    """Turn a card transfer into a subscription. Extends an active
    subscription rather than overwriting it, so paying twice adds up."""
    user = db.get(BotUser, telegram_user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")

    days = body.days or settings.subscription_days
    now = datetime.utcnow()
    base = (
        user.subscription_until
        if user.subscription_until and user.subscription_until > now
        else now
    )
    user.subscription_until = base + timedelta(days=days)

    db.add(
        Payment(
            telegram_user_id=telegram_user_id,
            amount=(
                body.amount_uzs
                if body.amount_uzs is not None
                else settings.subscription_price_uzs
            ),
            currency="UZS",
            method="card",
            granted_by=admin.id,
            note=body.note,
        )
    )
    db.commit()

    return {
        "telegram_user_id": telegram_user_id,
        "is_subscribed": True,
        "subscription_until": user.subscription_until.isoformat(),
        "days_added": days,
    }


@router.post("/users/{telegram_user_id}/revoke")
def revoke_subscription(
    telegram_user_id: int,
    db: Session = Depends(get_db),
    _: TelegramUser = Depends(require_admin),
):
    user = db.get(BotUser, telegram_user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    user.subscription_until = datetime.utcnow()
    db.commit()
    return {"telegram_user_id": telegram_user_id, "is_subscribed": False}


@router.get("/users/{telegram_user_id}/payments")
def user_payments(
    telegram_user_id: int,
    db: Session = Depends(get_db),
    _: TelegramUser = Depends(require_admin),
):
    rows = (
        db.execute(
            select(Payment)
            .where(Payment.telegram_user_id == telegram_user_id)
            .order_by(Payment.created_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(p.id),
            "amount": p.amount,
            "currency": p.currency,
            "method": p.method,
            "granted_by": p.granted_by,
            "note": p.note,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows
    ]
