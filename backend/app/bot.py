import uuid

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
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


@router.inline_query()
async def handle_inline_query(query: InlineQuery):
    session_id_str = query.query.strip()

    if not session_id_str:
        await query.answer([], cache_time=1)
        return

    try:
        session_id = uuid.UUID(session_id_str)
    except ValueError:
        await query.answer([], cache_time=1)
        return

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

    cur = session.currency or ""
    total_all = sum(float(p["total"]) for p in summary)

    # Build receipt text
    lines = ["🧾 <b>Bill Split</b>", ""]
    for person in summary:
        lines.append(f"👤 <b>{person['name']}</b>  —  <b>{cur}{person['total']}</b>")
        for item in person["items"]:
            lines.append(f"    • {item['name']}: {cur}{item['share']}")
        if float(person["extras"]) > 0:
            lines.append(f"    + tax/tip: {cur}{person['extras']}")
        lines.append("")

    lines.append(f"💰 <b>Total: {cur}{total_all:,.2f}</b>")
    text = "\n".join(lines)

    result = InlineQueryResultArticle(
        id=str(session_id),
        title="Send bill split to this chat",
        description=f"{len(summary)} people · {cur}{total_all:,.2f} total",
        input_message_content=InputTextMessageContent(
            message_text=text,
            parse_mode="HTML",
        ),
    )

    await query.answer([result], cache_time=300, is_personal=True)


async def process_update(update_data: dict):
    update = Update(**update_data)
    await dp.feed_update(bot, update)
