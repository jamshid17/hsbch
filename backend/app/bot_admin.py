"""Read-only view of the database, straight in the bot chat.

The Mini App dashboard is where things get *changed*; this is where they get
*watched* — no browser, no SSH, no psql. Every screen is one function that
returns (text, keyboard), so the same code answers both the command that
opens it and the inline button that refreshes or pages it.

Non-admins are not answered at all: the router-level filter drops their
updates, matching the /api/admin endpoints that 404 rather than 403 so the
panel never advertises its own existence.
"""

import logging
import re
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import Date, and_, cast, func, or_, select

from app.config import settings
from app.db import AsyncSessionLocal, async_engine
from app.models import Assignment, BotUser, Item, Payment, Person, ReceiptScan
from app.models import Session as SessionModel
from app.services.admin_auth import is_admin_async, is_super_admin
from app.timeutil import day_start_utc, to_local, today_local

logger = logging.getLogger(__name__)

# How many rows one screen shows. Eight two-line entries is about as much as
# fits on a phone without the keyboard scrolling off the bottom.
PAGE = 8
# Rows a /sql answer prints before it is cut off — a Telegram message caps at
# 4096 characters, and a wide table runs out of room long before 30 rows.
SQL_ROWS = 30

FILTERS = {
    "all": "Hammasi",
    "subscribed": "Obunachi",
    "exhausted": "Limit tugagan",
    "active": "Faol",
    "admins": "Admin",
}

ADMIN_COMMANDS = [
    ("admin", "Admin panel"),
    ("stats", "Statistika"),
    ("users", "Foydalanuvchilar"),
    ("find", "Foydalanuvchi qidirish"),
    ("payments", "To'lovlar"),
    ("sessions", "Sessiyalar"),
    ("tables", "Jadvallar va qatorlar soni"),
]


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user is not None and await is_admin_async(event.from_user.id)


router = Router(name="admin")
# Router-level, so a non-admin's update skips this router entirely and falls
# through to the ordinary handlers instead of getting an error.
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# --------------------------------------------------------------------------
# formatting helpers
# --------------------------------------------------------------------------


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _money(value: int | float | None) -> str:
    return f"{int(value or 0):,}".replace(",", " ")


def _dt(value: datetime | None) -> str:
    local = to_local(value)
    return local.strftime("%d.%m.%y %H:%M") if local else "—"


def _day(value: datetime | None) -> str:
    local = to_local(value)
    return local.strftime("%d.%m.%y") if local else "—"


def _ago(value: datetime | None) -> str:
    """Relative time from a naive-UTC column — what you actually want to read
    in a list of users."""
    if value is None:
        return "hech qachon"
    secs = int((datetime.utcnow() - value).total_seconds())
    if secs < 0:
        return "hozir"
    if secs < 60:
        return "hozir"
    if secs < 3600:
        return f"{secs // 60} daq oldin"
    if secs < 86400:
        return f"{secs // 3600} soat oldin"
    return f"{secs // 86400} kun oldin"


def _esc(value: str | None) -> str:
    """Names come from Telegram profiles and go into HTML messages, so they
    are escaped rather than trusted — a display name may contain < or &."""
    if not value:
        return ""
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _who(user: BotUser | None, telegram_user_id: int | None = None) -> str:
    if user is None:
        return f"id <code>{telegram_user_id}</code>"
    name = _esc(user.first_name) or "ismsiz"
    handle = f" @{_esc(user.username)}" if user.username else ""
    return f"{name}{handle}"


def _is_subscribed(user: BotUser, now: datetime) -> bool:
    return bool(user.subscription_until and user.subscription_until > now)


def _nav(prefix: str, offset: int, total: int, extra: str = "") -> list[InlineKeyboardButton]:
    """Prev/next row, showing which page of how many you are on."""
    buttons: list[InlineKeyboardButton] = []
    sep = f"{extra}:" if extra else ""
    if offset > 0:
        buttons.append(_b("◀️", f"a:{prefix}:{sep}{max(offset - PAGE, 0)}"))
    pages = max((total + PAGE - 1) // PAGE, 1)
    # Clamped: a keyboard left open while rows were deleted would otherwise
    # claim to be on page 5 of 4.
    page = min(offset // PAGE + 1, pages)
    buttons.append(_b(f"{page}/{pages}", "a:noop"))
    if offset + PAGE < total:
        buttons.append(_b("▶️", f"a:{prefix}:{sep}{offset + PAGE}"))
    return buttons


def _back(to: str = "a:menu") -> list[InlineKeyboardButton]:
    return [_b("⬅️ Menyu", to)]


# --------------------------------------------------------------------------
# screens
# --------------------------------------------------------------------------


def _menu_screen() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "🗄 <b>Admin panel</b>\n\n"
        "Bazadagi ma'lumotlarni shu yerdan kuzatib turasiz. "
        "Obuna berish/olish esa Mini App'dagi panelda."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [_b("📊 Statistika", "a:stats"), _b("👥 Foydalanuvchilar", "a:users:all:0")],
            [_b("💳 To'lovlar", "a:pay:0"), _b("🧾 Sessiyalar", "a:ses:0")],
            [_b("🗄 Jadvallar", "a:tables")],
        ]
    )
    return text, kb


async def _stats_screen(db) -> tuple[str, InlineKeyboardMarkup]:
    now = datetime.utcnow()
    today_start = day_start_utc()
    week_start = day_start_utc(6)

    async def count(model, *where) -> int:
        stmt = select(func.count()).select_from(model)
        if where:
            stmt = stmt.where(*where)
        return (await db.execute(stmt)).scalar_one()

    users_total = await count(BotUser)
    users_today = await count(BotUser, BotUser.created_at >= today_start)
    users_week = await count(BotUser, BotUser.created_at >= week_start)

    scans_total = await count(ReceiptScan)
    scans_today = await count(ReceiptScan, ReceiptScan.created_at >= today_start)
    scans_week = await count(ReceiptScan, ReceiptScan.created_at >= week_start)

    subscribed = await count(
        BotUser,
        BotUser.subscription_until.is_not(None),
        BotUser.subscription_until > now,
    )
    exhausted = await count(
        BotUser,
        BotUser.free_scans_used >= settings.free_total_scans,
        or_(
            BotUser.subscription_until.is_(None),
            BotUser.subscription_until <= now,
        ),
    )

    sessions_total = await count(SessionModel)

    month_start = day_start_utc(today_local().day - 1)
    revenue_month = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.created_at >= month_start, Payment.refunded_at.is_(None)
            )
        )
    ).scalar_one()
    payments_month = await count(
        Payment, Payment.created_at >= month_start, Payment.refunded_at.is_(None)
    )

    # Last 7 days of scans, zero-filled so a quiet day still shows as a gap
    # rather than silently disappearing from the chart.
    rows = (
        await db.execute(
            select(cast(ReceiptScan.created_at, Date).label("day"), func.count())
            .where(ReceiptScan.created_at >= day_start_utc(6))
            .group_by("day")
            .order_by("day")
        )
    ).all()
    by_day = {row[0]: row[1] for row in rows}
    days = [today_local() - timedelta(days=i) for i in range(6, -1, -1)]
    peak = max((by_day.get(d, 0) for d in days), default=0)
    chart = []
    for d in days:
        n = by_day.get(d, 0)
        filled = round(n / peak * 10) if peak else 0
        chart.append(f"{d.strftime('%d.%m')} {'█' * filled or '·'} {n}")

    sub_state = "✅ yoqilgan" if settings.subscriptions_enabled else "⛔️ o'chirilgan"

    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users_total}</b>\n"
        f"    bugun +{users_today} · 7 kunda +{users_week}\n\n"
        f"📷 Skanlar: <b>{scans_total}</b>\n"
        f"    bugun {scans_today} · 7 kunda {scans_week}\n\n"
        f"💎 Obunachilar: <b>{subscribed}</b> · limiti tugagan: {exhausted}\n"
        f"🧾 Sessiyalar: <b>{sessions_total}</b>\n"
        f"💰 Shu oy: <b>{_money(revenue_month)} UZS</b> ({payments_month} to'lov)\n"
        f"🔐 Obuna tizimi: {sub_state}\n\n"
        "<b>So'nggi 7 kun (skan)</b>\n"
        f"<pre>{chr(10).join(chart)}</pre>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[_b("🔄 Yangilash", "a:stats")], _back()]
    )
    return text, kb


async def _users_screen(
    db, flt: str, offset: int, search: str = ""
) -> tuple[str, InlineKeyboardMarkup]:
    now = datetime.utcnow()
    active_sub = and_(
        BotUser.subscription_until.is_not(None), BotUser.subscription_until > now
    )
    dead_sub = or_(
        BotUser.subscription_until.is_(None), BotUser.subscription_until <= now
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

    if flt == "subscribed":
        stmt = stmt.where(active_sub)
    elif flt == "exhausted":
        stmt = stmt.where(dead_sub, BotUser.free_scans_used >= settings.free_total_scans)
    elif flt == "active":
        stmt = stmt.where(BotUser.last_seen_at >= day_start_utc(6))
    elif flt == "admins":
        # The super admin is an admin by configuration, so they belong here
        # even if their row somehow has the column false.
        stmt = stmt.where(
            or_(
                BotUser.is_admin.is_(True),
                BotUser.telegram_user_id == (settings.super_admin_id or 0),
            )
        )

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    users = (
        (
            await db.execute(
                stmt.order_by(BotUser.last_seen_at.desc().nullslast())
                .limit(PAGE)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )

    head = f"👥 <b>Foydalanuvchilar</b> · {FILTERS.get(flt, flt)} · {total} ta"
    if search:
        head = f"🔎 <b>“{_esc(search)}”</b> · {total} ta topildi"

    lines = [head, ""]
    for i, u in enumerate(users, start=offset + 1):
        badges = ""
        if _is_subscribed(u, now):
            badges += " 💎"
        if u.is_admin or is_super_admin(u.telegram_user_id):
            badges += " 🛡"
        lines.append(f"<b>{i}.</b> {_who(u)}{badges} · <code>{u.telegram_user_id}</code>")
        lines.append(
            f"     📷 {u.scans_total} · bepul {u.free_scans_used}/"
            f"{settings.free_total_scans} · ⏱ {_ago(u.last_seen_at)}"
        )
    if not users:
        lines.append("<i>Hech narsa topilmadi.</i>")

    keyboard: list[list[InlineKeyboardButton]] = []
    # One numbered button per row above, four to a line — tapping opens the
    # full card without having to type an id.
    number_row: list[InlineKeyboardButton] = []
    for i, u in enumerate(users, start=offset + 1):
        number_row.append(_b(str(i), f"a:u:{u.telegram_user_id}"))
        if len(number_row) == 4:
            keyboard.append(number_row)
            number_row = []
    if number_row:
        keyboard.append(number_row)

    if not search:
        filter_row: list[InlineKeyboardButton] = []
        for key, label in FILTERS.items():
            mark = "• " if key == flt else ""
            filter_row.append(_b(f"{mark}{label}", f"a:users:{key}:0"))
            if len(filter_row) == 3:
                keyboard.append(filter_row)
                filter_row = []
        if filter_row:
            keyboard.append(filter_row)
        keyboard.append(_nav("users", offset, total, extra=flt))

    keyboard.append(_back())
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=keyboard)


async def _user_screen(db, telegram_user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    user = await db.get(BotUser, telegram_user_id)
    if user is None:
        return (
            f"Foydalanuvchi <code>{telegram_user_id}</code> topilmadi.",
            InlineKeyboardMarkup(inline_keyboard=[_back()]),
        )

    now = datetime.utcnow()
    sessions_hosted = (
        await db.execute(
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.telegram_chat_id == telegram_user_id)
        )
    ).scalar_one()
    scans = (
        await db.execute(
            select(func.count())
            .select_from(ReceiptScan)
            .where(ReceiptScan.telegram_user_id == telegram_user_id)
        )
    ).scalar_one()
    payments = (
        (
            await db.execute(
                select(Payment)
                .where(Payment.telegram_user_id == telegram_user_id)
                .order_by(Payment.created_at.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )

    if _is_subscribed(user, now):
        left = (user.subscription_until - now).days
        sub = f"✅ faol · {_day(user.subscription_until)} gacha ({left} kun)"
    elif user.subscription_until:
        sub = f"⛔️ tugagan · {_day(user.subscription_until)}"
    else:
        sub = "— yo'q"

    if is_super_admin(user.telegram_user_id):
        admin = "🛡 asosiy admin"
    elif user.is_admin:
        admin = "🛡 admin"
    else:
        admin = "—"

    lines = [
        f"👤 <b>{_who(user)}</b>",
        f"id: <code>{user.telegram_user_id}</code>",
        f"Ro'yxatdan: {_dt(user.created_at)}",
        f"Oxirgi kirish: {_dt(user.last_seen_at)} ({_ago(user.last_seen_at)})",
        "",
        f"📷 Skanlar: <b>{scans}</b> (hisoblagich: {user.scans_total})",
        f"🎁 Bepul ishlatilgan: {user.free_scans_used}/{settings.free_total_scans}",
        f"💎 Obuna: {sub}",
        f"🛡 Admin: {admin}",
        f"🧾 Host bo'lgan sessiyalar: {sessions_hosted}",
        "",
        f"💳 <b>To'lovlar</b> ({len(payments)} ta oxirgisi):",
    ]
    if payments:
        for p in payments:
            note = f" · {_esc(p.note)}" if p.note else ""
            refunded = " · ↩️ qaytarilgan" if p.refunded_at else ""
            lines.append(
                f"• {_money(p.amount)} {p.currency} · {p.method} · "
                f"{_dt(p.created_at)}{note}{refunded}"
            )
    else:
        lines.append("<i>yo'q</i>")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _b("🔄 Yangilash", f"a:u:{telegram_user_id}"),
                _b("👥 Ro'yxat", "a:users:all:0"),
            ],
            _back(),
        ]
    )
    return "\n".join(lines), kb


async def _payments_screen(db, offset: int) -> tuple[str, InlineKeyboardMarkup]:
    total = (
        await db.execute(select(func.count()).select_from(Payment))
    ).scalar_one()
    rows = (
        await db.execute(
            select(Payment, BotUser)
            .outerjoin(BotUser, BotUser.telegram_user_id == Payment.telegram_user_id)
            .order_by(Payment.created_at.desc())
            .limit(PAGE)
            .offset(offset)
        )
    ).all()
    earned = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.refunded_at.is_(None)
            )
        )
    ).scalar_one()

    lines = [
        f"💳 <b>To'lovlar</b> · {total} ta · jami {_money(earned)} UZS",
        "",
    ]
    keyboard: list[list[InlineKeyboardButton]] = []
    number_row: list[InlineKeyboardButton] = []
    for i, (p, u) in enumerate(rows, start=offset + 1):
        refunded = " ↩️" if p.refunded_at else ""
        note = f"\n     💬 {_esc(p.note)}" if p.note else ""
        lines.append(
            f"<b>{i}.</b> {_money(p.amount)} {p.currency} · {p.method}{refunded}\n"
            f"     👤 {_who(u, p.telegram_user_id)} · {_dt(p.created_at)}{note}"
        )
        number_row.append(_b(str(i), f"a:u:{p.telegram_user_id}"))
        if len(number_row) == 4:
            keyboard.append(number_row)
            number_row = []
    if number_row:
        keyboard.append(number_row)
    if not rows:
        lines.append("<i>Hali to'lov yo'q.</i>")

    keyboard.append(_nav("pay", offset, total))
    keyboard.append(_back())
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=keyboard)


async def _sessions_screen(db, offset: int) -> tuple[str, InlineKeyboardMarkup]:
    total = (
        await db.execute(select(func.count()).select_from(SessionModel))
    ).scalar_one()
    items_ct = (
        select(func.count())
        .where(Item.session_id == SessionModel.id)
        .scalar_subquery()
    )
    people_ct = (
        select(func.count())
        .where(Person.session_id == SessionModel.id)
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(SessionModel, items_ct, people_ct, BotUser)
            .outerjoin(
                BotUser, BotUser.telegram_user_id == SessionModel.telegram_chat_id
            )
            .order_by(SessionModel.created_at.desc())
            .limit(PAGE)
            .offset(offset)
        )
    ).all()

    lines = [f"🧾 <b>Sessiyalar</b> · {total} ta", ""]
    keyboard: list[list[InlineKeyboardButton]] = []
    number_row: list[InlineKeyboardButton] = []
    for i, (s, n_items, n_people, host) in enumerate(rows, start=offset + 1):
        title = f" · {_esc(s.title)}" if s.title else ""
        mode = "🤝" if s.assignment_mode == "collaborative" else "👑"
        lines.append(
            f"<b>{i}.</b> <code>{s.code}</code> · {s.status} {mode}{title}\n"
            f"     🍽 {n_items} mahsulot · 👥 {n_people} kishi · "
            f"{s.currency or '—'} · {_dt(s.created_at)}\n"
            f"     👤 {_who(host, s.telegram_chat_id)}"
        )
        number_row.append(_b(str(i), f"a:u:{s.telegram_chat_id}"))
        if len(number_row) == 4:
            keyboard.append(number_row)
            number_row = []
    if number_row:
        keyboard.append(number_row)
    if not rows:
        lines.append("<i>Hali sessiya yo'q.</i>")

    keyboard.append(_nav("ses", offset, total))
    keyboard.append(_back())
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=keyboard)


async def _tables_screen(db) -> tuple[str, InlineKeyboardMarkup]:
    tables = [
        ("bot_users", BotUser, "foydalanuvchi"),
        ("sessions", SessionModel, "sessiya"),
        ("items", Item, "mahsulot"),
        ("people", Person, "ishtirokchi"),
        ("assignments", Assignment, "tanlov"),
        ("payments", Payment, "to'lov"),
        ("receipt_scans", ReceiptScan, "skan"),
    ]
    lines = ["🗄 <b>Jadvallar</b>", ""]
    for name, model, label in tables:
        n = (await db.execute(select(func.count()).select_from(model))).scalar_one()
        lines.append(f"<code>{name:<14}</code> {n:>6}  <i>{label}</i>")

    size = (
        await db.execute(
            select(func.pg_size_pretty(func.pg_database_size(settings.postgres_db)))
        )
    ).scalar_one()
    version = (
        await db.execute(select(func.current_setting("server_version")))
    ).scalar_one()
    lines += ["", f"💾 Baza hajmi: <b>{size}</b>", f"🐘 PostgreSQL {version}"]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[_b("🔄 Yangilash", "a:tables")], _back()]
    )
    return "\n".join(lines), kb


SCREENS = {
    "stats": _stats_screen,
    "tables": _tables_screen,
}


# --------------------------------------------------------------------------
# handlers
# --------------------------------------------------------------------------


async def _send(message: Message, rendered: tuple[str, InlineKeyboardMarkup]):
    text, kb = rendered
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


async def _edit(cq: CallbackQuery, rendered: tuple[str, InlineKeyboardMarkup]):
    text, kb = rendered
    try:
        await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except TelegramBadRequest as exc:
        # Refreshing a screen nothing has changed on is a no-op, not an error.
        if "message is not modified" not in str(exc):
            raise


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await _send(message, _menu_screen())


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    async with AsyncSessionLocal() as db:
        await _send(message, await _stats_screen(db))


@router.message(Command("users"))
async def cmd_users(message: Message):
    async with AsyncSessionLocal() as db:
        await _send(message, await _users_screen(db, "all", 0))


@router.message(Command("find"))
async def cmd_find(message: Message, command: CommandObject):
    query = (command.args or "").strip()
    if not query:
        await message.answer(
            "Foydalanish: <code>/find ali</code> yoki <code>/find 123456789</code>",
            parse_mode="HTML",
        )
        return
    async with AsyncSessionLocal() as db:
        await _send(message, await _users_screen(db, "all", 0, search=query))


@router.message(Command("payments"))
async def cmd_payments(message: Message):
    async with AsyncSessionLocal() as db:
        await _send(message, await _payments_screen(db, 0))


@router.message(Command("sessions"))
async def cmd_sessions(message: Message):
    async with AsyncSessionLocal() as db:
        await _send(message, await _sessions_screen(db, 0))


@router.message(Command("tables"))
async def cmd_tables(message: Message):
    async with AsyncSessionLocal() as db:
        await _send(message, await _tables_screen(db))


@router.message(Command("sql"))
async def cmd_sql(message: Message, command: CommandObject):
    """Arbitrary read-only SELECT, super admin only.

    Three things keep this from being a way to lose the database: only the
    owner account may run it, only a single SELECT/WITH statement is accepted,
    and it runs inside a READ ONLY transaction that is always rolled back —
    so even a query that talks its way past the regex cannot write.
    """
    if not is_super_admin(message.from_user.id):
        await message.answer("Bu buyruq faqat asosiy admin uchun.")
        return

    query = (command.args or "").strip().rstrip(";").strip()
    if not query:
        await message.answer(
            "Foydalanish:\n"
            "<code>/sql select code, status from sessions order by created_at desc limit 5</code>",
            parse_mode="HTML",
        )
        return
    if ";" in query:
        await message.answer("Faqat bitta so'rov yuboring.")
        return
    if not re.match(r"^(select|with)\b", query, re.IGNORECASE):
        await message.answer("Faqat <code>SELECT</code> so'rovlariga ruxsat.", parse_mode="HTML")
        return
    if not re.search(r"\blimit\b", query, re.IGNORECASE):
        query = f"{query} LIMIT {SQL_ROWS + 1}"

    try:
        columns, rows = await run_readonly_sql(query)
    except Exception as exc:  # noqa: BLE001 — the error text is the answer
        await message.answer(f"❌ <pre>{_esc(str(exc)[:600])}</pre>", parse_mode="HTML")
        return

    await message.answer(_render_rows(columns, rows), parse_mode="HTML")


async def run_readonly_sql(query: str) -> tuple[list[str], list]:
    """Run one statement in a transaction that is READ ONLY and always rolled
    back — the belt and braces behind the regex in cmd_sql."""
    async with async_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            await conn.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
            result = await conn.exec_driver_sql(query)
            return list(result.keys()), result.fetchmany(SQL_ROWS)
        finally:
            await trans.rollback()


def _render_rows(columns: list[str], rows: list) -> str:
    """Fixed-width table that survives Telegram's <pre> block."""
    if not rows:
        return "🔍 <i>Natija yo'q.</i>"

    def cell(value) -> str:
        if value is None:
            return "—"
        out = str(value)
        return out[:21] + "…" if len(out) > 22 else out

    table = [[str(c) for c in columns]] + [[cell(v) for v in row] for row in rows]
    widths = [max(len(r[i]) for r in table) for i in range(len(columns))]
    lines = [
        "  ".join(value.ljust(widths[i]) for i, value in enumerate(table[0])),
        "  ".join("-" * w for w in widths),
    ]
    for row in table[1:]:
        lines.append("  ".join(value.ljust(widths[i]) for i, value in enumerate(row)))

    body = "\n".join(lines)
    if len(body) > 3500:
        body = body[:3500] + "\n… (uzun natija qisqartirildi)"
    note = f"\n\n{len(rows)} qator" + (" (birinchi sahifa)" if len(rows) >= SQL_ROWS else "")
    return f"<pre>{_esc(body)}</pre>{note}"


async def render_callback(data: str) -> tuple[str, InlineKeyboardMarkup] | None:
    """Turn a button's callback_data back into the screen it names.

    None means "nothing to redraw" — either the page counter, which is a
    label rather than a button, or callback_data this build doesn't know.
    """
    parts = data.split(":")
    screen = parts[1] if len(parts) > 1 else "menu"

    if screen == "noop":
        return None
    if screen == "menu":
        return _menu_screen()

    async with AsyncSessionLocal() as db:
        if screen in SCREENS:
            return await SCREENS[screen](db)
        if screen == "users":
            return await _users_screen(db, parts[2], int(parts[3]))
        if screen == "u":
            return await _user_screen(db, int(parts[2]))
        if screen == "pay":
            return await _payments_screen(db, int(parts[2]))
        if screen == "ses":
            return await _sessions_screen(db, int(parts[2]))
    return None


@router.callback_query(F.data.startswith("a:"))
async def on_admin_callback(cq: CallbackQuery):
    try:
        rendered = await render_callback(cq.data)
    except (IndexError, ValueError):
        # Stale keyboard from an older build — say so rather than dying
        # silently on a button that no longer parses.
        await cq.answer("Eski tugma. /admin ni qaytadan oching.", show_alert=True)
        return

    if rendered is not None:
        await _edit(cq, rendered)
    await cq.answer()


async def sync_admin_commands(bot: Bot, chat_id: int, telegram_user_id: int) -> bool:
    """Put the admin commands in this chat's ⌘ menu — and only this chat's.

    Scoped per chat rather than globally so ordinary users never see that the
    commands exist. Called on every /start, which is also what takes them away
    again from someone who has just been demoted.
    """
    admin = await is_admin_async(telegram_user_id)
    try:
        scope = BotCommandScopeChat(chat_id=chat_id)
        if admin:
            await bot.set_my_commands(
                [BotCommand(command=c, description=d) for c, d in ADMIN_COMMANDS],
                scope=scope,
            )
        else:
            await bot.delete_my_commands(scope=scope)
    except TelegramBadRequest:
        # A cosmetic menu is never worth failing /start over.
        logger.warning("could not sync admin commands for %s", chat_id, exc_info=True)
    return admin
