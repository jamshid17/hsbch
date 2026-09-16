import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.db import get_db
from app.models import BotUser, Payment, ReceiptScan
from app.models import Session as SessionModel
from app.services.admin_auth import is_super_admin, require_admin
from app.services.telegram_auth import TelegramUser
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Date, case, cast, func, or_, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

TASHKENT = ZoneInfo("Asia/Tashkent")


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
        # Admins in the table, plus the super admin — who is one by
        # configuration and may not have a row at all yet.
        "admins_total": len(
            {
                u
                for u in db.execute(
                    select(BotUser.telegram_user_id).where(BotUser.is_admin.is_(True))
                ).scalars()
            }
            | ({settings.super_admin_id} if settings.super_admin_id else set())
        ),
        "subscriptions_enabled": settings.subscriptions_enabled,
    }


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _: TelegramUser = Depends(require_admin),
    search: str = "",
    filter: str = Query("all", pattern="^(all|subscribed|exhausted|active|admins)$"),
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
    elif filter == "admins":
        # The super admin is an admin by configuration, so they belong here
        # even if their row somehow has the column false.
        stmt = stmt.where(
            or_(
                BotUser.is_admin.is_(True),
                BotUser.telegram_user_id == (settings.super_admin_id or 0),
            )
        )

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
                "is_admin": bool(u.is_admin) or is_super_admin(u.telegram_user_id),
                # The owner account — shown differently and never demotable.
                "is_super_admin": is_super_admin(u.telegram_user_id),
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


class AdminFlagIn(BaseModel):
    is_admin: bool


@router.post("/users/{telegram_user_id}/admin")
def set_admin(
    telegram_user_id: int,
    body: AdminFlagIn,
    db: Session = Depends(get_db),
    admin: TelegramUser = Depends(require_admin),
):
    """Promote someone to admin, or take it away — the whole point being that
    this no longer needs an .env edit and a redeploy.

    Two things are refused outright, both to keep the panel reachable: the
    super admin can't be demoted by anyone, themselves included — they are the
    owner account and the guarantee that someone can always get in; and nobody
    can demote themselves, which is the one mistake that locks the current
    session out of the screen it was clicking on.
    """
    if is_super_admin(telegram_user_id) and not body.is_admin:
        raise HTTPException(
            400,
            "Bu foydalanuvchi — asosiy admin. Uni adminlikdan olib "
            "tashlab bo'lmaydi.",
        )
    if telegram_user_id == admin.id and not body.is_admin:
        raise HTTPException(
            400, "O'zingizni adminlikdan olib tashlay olmaysiz."
        )

    user = db.get(BotUser, telegram_user_id)
    if user is None:
        if not body.is_admin:
            raise HTTPException(404, "Foydalanuvchi topilmadi")
        # Promoting someone who has never opened the Mini App: create the row
        # now rather than making them log in first and be searched for
        # afterwards. Their name fills itself in the moment they do open it,
        # and this is what lets an admin be added from a bare Telegram id.
        user = BotUser(telegram_user_id=telegram_user_id)
        db.add(user)

    user.is_admin = body.is_admin
    db.commit()
    logger.info(
        "admin %s set is_admin=%s for %s", admin.id, body.is_admin, telegram_user_id
    )
    return {
        "telegram_user_id": telegram_user_id,
        "is_admin": bool(user.is_admin) or is_super_admin(telegram_user_id),
        "is_super_admin": is_super_admin(telegram_user_id),
    }
