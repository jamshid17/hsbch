import logging
from datetime import datetime, timedelta

from app.config import settings
from app.db import get_db
from app.models import Assignment, BotUser, Item, Payment, Person, ReceiptScan
from app.models import Session as SessionModel
from app.permissions import ALL_PERMISSIONS, Permission, clean
from app.services.admin_auth import (
    is_super_admin,
    permissions_of,
    require_admin,
    require_permission,
)
from app.services.telegram_auth import TelegramUser
from app.timeutil import day_start_utc as _day_start_utc
from app.timeutil import today_local as _today
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Date, case, cast, func, or_, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
                # Everything for the owner, whatever the column happens to
                # hold; nothing for anyone who isn't an admin.
                "permissions": (
                    sorted(ALL_PERMISSIONS)
                    if is_super_admin(u.telegram_user_id)
                    else clean(u.permissions) if u.is_admin else []
                ),
                "is_blocked": u.blocked_at is not None,
                "blocked_at": u.blocked_at.isoformat() if u.blocked_at else None,
                "block_reason": u.block_reason,
            }
            for u in users
        ],
    }


def _user_brief(user: BotUser | None, telegram_user_id: int) -> dict:
    """Just enough of a bot_users row to label a payment or a session — the
    id always resolves, the name only if they have ever opened the app."""
    return {
        "telegram_user_id": telegram_user_id,
        "first_name": user.first_name if user else None,
        "username": user.username if user else None,
    }


@router.get("/payments")
def list_payments(
    db: Session = Depends(get_db),
    _: TelegramUser = Depends(require_permission(Permission.PAYMENTS)),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Every payment, newest first — the ledger behind the revenue tile."""
    total = db.execute(select(func.count()).select_from(Payment)).scalar_one()
    revenue_total = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.refunded_at.is_(None)
        )
    ).scalar_one()

    rows = db.execute(
        select(Payment, BotUser)
        .outerjoin(BotUser, BotUser.telegram_user_id == Payment.telegram_user_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "total": total,
        "revenue_total": int(revenue_total),
        "payments": [
            {
                "id": str(p.id),
                "amount": p.amount,
                "currency": p.currency,
                "method": p.method,
                "granted_by": p.granted_by,
                "note": p.note,
                "refunded_at": p.refunded_at.isoformat() if p.refunded_at else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "user": _user_brief(u, p.telegram_user_id),
            }
            for p, u in rows
        ],
    }


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    _: TelegramUser = Depends(require_permission(Permission.SESSIONS)),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Recent bills, newest first. The item and people counts are correlated
    subqueries rather than a join, so a session with no items still shows up."""
    total = db.execute(select(func.count()).select_from(SessionModel)).scalar_one()

    items_count = (
        select(func.count()).where(Item.session_id == SessionModel.id).scalar_subquery()
    )
    people_count = (
        select(func.count())
        .where(Person.session_id == SessionModel.id)
        .scalar_subquery()
    )

    rows = db.execute(
        select(SessionModel, items_count, people_count, BotUser)
        .outerjoin(BotUser, BotUser.telegram_user_id == SessionModel.telegram_chat_id)
        .order_by(SessionModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "total": total,
        "sessions": [
            {
                "id": str(s.id),
                "code": s.code,
                "status": s.status,
                "title": s.title,
                "currency": s.currency,
                "assignment_mode": s.assignment_mode,
                "items_count": n_items,
                "people_count": n_people,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "host": _user_brief(host, s.telegram_chat_id),
            }
            for s, n_items, n_people, host in rows
        ],
    }


@router.get("/tables")
def list_tables(
    db: Session = Depends(get_db),
    _: TelegramUser = Depends(require_permission(Permission.TABLES)),
):
    """Row counts per table, plus how much disk the whole thing takes — the
    "is anything actually in there" view you'd otherwise open psql for."""
    models = [
        ("bot_users", BotUser),
        ("sessions", SessionModel),
        ("items", Item),
        ("people", Person),
        ("assignments", Assignment),
        ("payments", Payment),
        ("receipt_scans", ReceiptScan),
    ]
    return {
        "tables": [
            {
                "name": name,
                "rows": db.execute(
                    select(func.count()).select_from(model)
                ).scalar_one(),
            }
            for name, model in models
        ],
        "db_size": db.execute(
            select(func.pg_size_pretty(func.pg_database_size(settings.postgres_db)))
        ).scalar_one(),
        "pg_version": db.execute(
            select(func.current_setting("server_version"))
        ).scalar_one(),
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
    admin: TelegramUser = Depends(require_permission(Permission.SUBSCRIPTIONS)),
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
    _: TelegramUser = Depends(require_permission(Permission.SUBSCRIPTIONS)),
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
    _: TelegramUser = Depends(require_permission(Permission.PAYMENTS)),
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


class BlockIn(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


def _target(db: Session, telegram_user_id: int) -> BotUser:
    user = db.get(BotUser, telegram_user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return user


def _refuse_if_protected(
    db: Session, admin: TelegramUser, telegram_user_id: int, action: str
) -> None:
    """The two people nobody may lock out, and the one rule above that.

    The owner account is the guarantee that someone can always get into the
    panel; blocking it would throw that away as thoroughly as demoting it.
    Blocking yourself locks you out of the screen you are standing on. And an
    admin is only blockable by someone who could have demoted them anyway —
    otherwise the weaker grant quietly does the stronger one's job.
    """
    if is_super_admin(telegram_user_id):
        raise HTTPException(400, f"Asosiy adminni {action} mumkin emas.")
    if telegram_user_id == admin.id:
        raise HTTPException(400, f"O'zingizni {action} mumkin emas.")
    target = db.get(BotUser, telegram_user_id)
    if (
        target is not None
        and target.is_admin
        and Permission.MANAGE_ADMINS.value not in permissions_of(db, admin.id)
    ):
        raise HTTPException(403, f"Adminni {action} uchun huquqingiz yo'q.")


@router.post("/users/{telegram_user_id}/block")
def block_user(
    telegram_user_id: int,
    body: BlockIn,
    db: Session = Depends(get_db),
    admin: TelegramUser = Depends(require_permission(Permission.BLOCK_USERS)),
):
    """Shut someone out of the app and the bot.

    Nothing of theirs is touched — their bills, their picks and their
    subscription all stay exactly where they were, so unblocking is a plain
    undo rather than a restore.
    """
    _refuse_if_protected(db, admin, telegram_user_id, "bloklash")
    user = _target(db, telegram_user_id)

    if user.blocked_at is None:
        user.blocked_at = datetime.utcnow()
        user.blocked_by = admin.id
    # A reason given on a re-block replaces the old one; the timestamp stays
    # the first one, which is the answer to "since when".
    user.block_reason = (body.reason or "").strip() or None
    db.commit()
    logger.info(
        "admin %s blocked %s (%s)", admin.id, telegram_user_id, user.block_reason
    )
    return {
        "telegram_user_id": telegram_user_id,
        "is_blocked": True,
        "blocked_at": user.blocked_at.isoformat(),
        "block_reason": user.block_reason,
    }


@router.post("/users/{telegram_user_id}/unblock")
def unblock_user(
    telegram_user_id: int,
    db: Session = Depends(get_db),
    admin: TelegramUser = Depends(require_permission(Permission.BLOCK_USERS)),
):
    user = _target(db, telegram_user_id)
    user.blocked_at = None
    user.blocked_by = None
    user.block_reason = None
    # A fresh start, or the next stray photo would block them straight back.
    user.not_receipt_strikes = 0
    db.commit()
    logger.info("admin %s unblocked %s", admin.id, telegram_user_id)
    return {"telegram_user_id": telegram_user_id, "is_blocked": False}


class PermissionsIn(BaseModel):
    permissions: list[str]


@router.post("/users/{telegram_user_id}/permissions")
def set_permissions(
    telegram_user_id: int,
    body: PermissionsIn,
    db: Session = Depends(get_db),
    admin: TelegramUser = Depends(require_permission(Permission.MANAGE_ADMINS)),
):
    """Replace what an admin may do (app/permissions.py).

    Two rules hold it together. The owner account's rights are implicit, so
    there is nothing here to edit and editing it would only create a column
    that disagrees with the code. And nobody can grant what they don't hold
    themselves — otherwise MANAGE_ADMINS alone would be every permission,
    reachable by promoting a second account and granting it everything.
    """
    unknown = sorted(set(body.permissions) - ALL_PERMISSIONS)
    if unknown:
        raise HTTPException(400, f"Noma'lum huquq: {', '.join(unknown)}")

    if is_super_admin(telegram_user_id):
        raise HTTPException(
            400, "Asosiy adminda barcha huquqlar doimiy — o'zgartirib bo'lmaydi."
        )

    user = _target(db, telegram_user_id)
    if not user.is_admin:
        raise HTTPException(400, "Avval foydalanuvchini admin qiling.")

    mine = permissions_of(db, admin.id)
    granting = set(body.permissions) - set(clean(user.permissions))
    beyond = sorted(granting - mine)
    if beyond:
        raise HTTPException(
            403, f"O'zingizda yo'q huquqni bera olmaysiz: {', '.join(beyond)}"
        )

    user.permissions = clean(body.permissions)
    db.commit()
    logger.info(
        "admin %s set permissions %s for %s",
        admin.id,
        user.permissions,
        telegram_user_id,
    )
    return {
        "telegram_user_id": telegram_user_id,
        "permissions": user.permissions,
    }


class AdminFlagIn(BaseModel):
    is_admin: bool


@router.post("/users/{telegram_user_id}/admin")
def set_admin(
    telegram_user_id: int,
    body: AdminFlagIn,
    db: Session = Depends(get_db),
    admin: TelegramUser = Depends(require_permission(Permission.MANAGE_ADMINS)),
):
    """Promote someone to admin, or take it away — the whole point being that
    this no longer needs an .env edit and a redeploy.

    Behind the MANAGE_ADMINS grant, which the owner holds implicitly and can
    hand on. Two things are refused outright whoever asks, both to keep the
    panel reachable: the super
    admin can't be demoted by anyone, themselves included — they are the
    guarantee that someone can always get in; and nobody can demote
    themselves, which is the one mistake that locks the current session out of
    the screen it was clicking on.
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
    if not body.is_admin:
        # Otherwise promoting them again later would silently hand back
        # everything they had the first time.
        user.permissions = []
    db.commit()
    logger.info(
        "admin %s set is_admin=%s for %s", admin.id, body.is_admin, telegram_user_id
    )
    return {
        "telegram_user_id": telegram_user_id,
        "is_admin": bool(user.is_admin) or is_super_admin(telegram_user_id),
        "is_super_admin": is_super_admin(telegram_user_id),
    }
