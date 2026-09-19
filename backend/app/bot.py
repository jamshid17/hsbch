import html
import uuid
from decimal import Decimal

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultCachedPhoto,
    InputTextMessageContent,
    MenuButtonWebApp,
    Message,
    Update,
    WebAppInfo,
)
from sqlalchemy import select

from app.bot_admin import router as admin_router
from app.bot_admin import sync_admin_commands
from app.calculator import calculate_summary
from app.config import settings
from app.db import AsyncSessionLocal
from app.models import Assignment, Item, Person
from app.models import Session as SessionModel

bot = Bot(token=settings.bot_token)
dp = Dispatcher()
router = Router()
dp.include_router(router)
# Admin-only screens over the database. Its own router-level filter drops
# everyone else's updates, so ordering against the public handlers is safe.
dp.include_router(admin_router)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    await bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonWebApp(
            text="Split Bill",
            web_app=WebAppInfo(url=settings.webapp_url),
        ),
    )

    # Keeps the ⌘ menu in step with who is an admin *now* — granted on this
    # chat only, and taken away again the next /start after a demotion.
    is_admin = await sync_admin_commands(bot, message.chat.id, message.from_user.id)

    raw_arg = (command.args or "").strip()

    # Deep link: /start <CODE> (from t.me/<bot>?start=<CODE>) opens the Mini App
    # straight into the join screen for that session.
    code = raw_arg.upper()
    if code:
        sep = "&" if "?" in settings.webapp_url else "?"
        join_url = f"{settings.webapp_url}{sep}join={code}"
        await message.answer(
            f"You've been invited to split a bill. Tap to join code <b>{code}</b>.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"Join bill {code}",
                            web_app=WebAppInfo(url=join_url),
                        )
                    ]
                ]
            ),
        )
        return

    text = "Tap the menu button below to open the bill splitter."
    if is_admin:
        text += "\n\n🗄 Admin: /admin — bazani shu yerdan kuzatib turasiz."
    await message.answer(text)


# The inline message is composed by the bot, not the Mini App, so it carries
# its own copies of the few phrases it needs. The Mini App appends its chosen
# language to the inline query ("<uuid>|uz"); failing that we fall back to the
# user's Telegram language, then to Uzbek — the app's own default.
INLINE_LABELS = {
    "uz": {
        "title": "Kim qancha to'laydi",
        "grand": "Jami",
        "how": "Qanday hisoblanganini ko'rish",
        "as_text": "📄 Ro'yxat sifatida yuborish",
        "as_photo": "🖼 Rasm sifatida yuborish",
        "people": "{n} kishi",
    },
    "ru": {
        "title": "Кто сколько должен",
        "grand": "Итого",
        "how": "Посмотреть, как посчитано",
        "as_text": "📄 Отправить списком",
        "as_photo": "🖼 Отправить картинкой",
        "people": "{n} чел.",
    },
    "en": {
        "title": "Who owes what",
        "grand": "Grand total",
        "how": "See how it was calculated",
        "as_text": "📄 Send as a list",
        "as_photo": "🖼 Send as a picture",
        "people": "{n} people",
    },
}


def _labels(explicit: str, telegram_lang: str | None) -> dict:
    for code in (explicit, (telegram_lang or "").split("-")[0], "uz"):
        if code in INLINE_LABELS:
            return INLINE_LABELS[code]
    return INLINE_LABELS["uz"]


def _esc(text: str) -> str:
    """Escape for Telegram's HTML parse mode — only & < >.

    Not html.escape()'s default: that also turns an apostrophe into &#x27;,
    a numeric entity Telegram doesn't decode, so half the Uzbek names and
    labels in this app would arrive with the escape showing.
    """
    return html.escape(text, quote=False)


def _fmt(value) -> str:
    """Space-grouped thousands, comma decimals, .00 dropped — the same shape
    the Mini App shows, so the shared message matches the screen it came from.
    Non-breaking spaces, so a total never wraps mid-number.
    """
    amount = Decimal(str(value))
    if amount == amount.to_integral_value():
        text = f"{int(amount):,}"
    else:
        text = f"{amount:,.2f}"
    return text.replace(",", "\u00a0").replace(".", ",")


_bot_username: str | None = None


async def _deep_link(code: str) -> str | None:
    """t.me/<bot>?startapp=<code> — the link behind "see how it was
    calculated". None if Telegram won't tell us the username."""
    global _bot_username
    if _bot_username is None:
        try:
            _bot_username = (await bot.me()).username
        except Exception:
            return None
    return f"https://t.me/{_bot_username}?startapp={code}"


@router.inline_query()
async def handle_inline_query(query: InlineQuery):
    # "<session uuid>" or "<session uuid>|<language>" — the Mini App appends
    # the language it is being read in, which the bot has no other way to know.
    raw, _, lang = query.query.strip().partition("|")

    if not raw:
        await query.answer([], cache_time=1)
        return

    try:
        session_id = uuid.UUID(raw)
    except ValueError:
        await query.answer([], cache_time=1)
        return

    L = _labels(lang.strip().lower(), query.from_user.language_code)

    async with AsyncSessionLocal() as db:
        session = await db.get(SessionModel, session_id)
        if not session or session.status != "done":
            await query.answer([], cache_time=1)
            return

        items_r = await db.execute(select(Item).where(Item.session_id == session_id))
        items = items_r.scalars().all()

        people_r = await db.execute(select(Person).where(Person.session_id == session_id))
        people = people_r.scalars().all()

        if not items or not people:
            await query.answer([], cache_time=1)
            return

        item_ids = [i.id for i in items]
        assign_r = await db.execute(
            select(Assignment).where(Assignment.item_id.in_(item_ids))
        )
        assignments = assign_r.scalars().all()

        summary = calculate_summary(session, items, people, assignments)
        image_file_id = session.summary_image_file_id

    cur = session.currency or ""
    total_all = sum(Decimal(str(p["total"])) for p in summary)
    heading = _esc(session.title or L["title"])
    description = f"{L['people'].format(n=len(summary))} · {_fmt(total_all)} {cur}".strip()

    # The full breakdown lives behind the deep link, so the message itself
    # stays a short list of who owes what.
    lines = []
    link = await _deep_link(session.code)
    if link:
        lines.append(f'🔎 <a href="{link}">{L["how"]}</a>')
        lines.append("")
    lines.append(f"🧾 <b>{heading}</b>")
    for person in summary:
        owed = f"{_fmt(person['total'])} {cur}".strip()
        lines.append(f"{_esc(person['name'])}: <b>{owed}</b>")
    lines.append("")
    grand = f"{_fmt(total_all)} {cur}".strip()
    lines.append(f"💰 <b>{L['grand']}: {grand}</b>")
    text = "\n".join(lines)

    # The picture already spells out every line, so its caption only repeats
    # the headline and the link. (Telegram caps captions at 1024 chars.)
    caption_lines = [f"🧾 <b>{heading}</b> — {grand}"]
    if link:
        caption_lines.append(f'🔎 <a href="{link}">{L["how"]}</a>')
    caption = "\n".join(caption_lines)

    results = [
        InlineQueryResultArticle(
            id=str(session_id),
            title=L["as_text"],
            description=description,
            input_message_content=InputTextMessageContent(
                message_text=text,
                parse_mode="HTML",
            ),
        )
    ]

    # The Mini App rendered a card for this split — offer the picture too; in
    # a group it reads far better than the same numbers as text.
    if image_file_id:
        results.append(
            InlineQueryResultCachedPhoto(
                id=f"{session_id}-photo",
                photo_file_id=image_file_id,
                title=L["as_photo"],
                description=description,
                caption=caption,
                parse_mode="HTML",
            )
        )

    await query.answer(results, cache_time=300, is_personal=True)


async def process_update(update_data: dict):
    update = Update(**update_data)
    await dp.feed_update(bot, update)
