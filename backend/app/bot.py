import uuid

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    MenuButtonWebApp,
    Message,
    Update,
    WebAppInfo,
)
from sqlalchemy import select

from app.calculator import calculate_summary
from app.config import settings
from app.db import AsyncSessionLocal
from app.models import Assignment, Item, Person
from app.models import Session as SessionModel

bot = Bot(token=settings.bot_token)
dp = Dispatcher()
router = Router()
dp.include_router(router)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonWebApp(
            text="Split Bill",
            web_app=WebAppInfo(url=settings.webapp_url),
        ),
    )
    await message.answer("Tap the menu button below to open the bill splitter.")


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
