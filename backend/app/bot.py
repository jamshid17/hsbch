import uuid
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LabeledPrice,
    MenuButtonWebApp,
    Message,
    PreCheckoutQuery,
    Update,
    WebAppInfo,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.calculator import calculate_summary
from app.config import settings
from app.db import AsyncSessionLocal
from app.models import Assignment, BotUser, Item, Payment, Person
from app.models import Session as SessionModel

bot = Bot(token=settings.bot_token)
dp = Dispatcher()
router = Router()
dp.include_router(router)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    await bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonWebApp(
            text="Split Bill",
            web_app=WebAppInfo(url=settings.webapp_url),
        ),
    )

    # Deep link: /start subscribe (from the Mini App's quota-exceeded button)
    # sends the subscription invoice right here in the chat.
    raw_arg = (command.args or "").strip()
    if raw_arg.lower() == "subscribe":
        await send_subscription_invoice(message)
        return

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

    await message.answer("Tap the menu button below to open the bill splitter.")


async def send_subscription_invoice(message: Message):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="30 kunlik cheksiz skanerlash",
        description=(
            f"{settings.subscription_days} kun davomida kunlik limitsiz "
            "chek skanerlash imkoniyati."
        ),
        payload=f"subscription:{message.from_user.id}",
        provider_token=settings.payment_provider_token,
        currency="UZS",
        prices=[
            LabeledPrice(label="Obuna", amount=settings.subscription_price_uzs * 100)
        ],
    )


@router.pre_checkout_query()
async def handle_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    # Digital service, always in stock — nothing to validate, just approve.
    # Telegram requires an answer within 10 seconds or the payment is cancelled.
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def handle_successful_payment(message: Message):
    sp = message.successful_payment
    user_id = message.from_user.id

    async with AsyncSessionLocal() as db:
        exists = (
            await db.execute(
                select(Payment).where(
                    Payment.telegram_payment_charge_id == sp.telegram_payment_charge_id
                )
            )
        ).scalar_one_or_none()
        if exists:
            # Telegram redelivered an already-processed successful_payment.
            return

        db.add(
            Payment(
                telegram_user_id=user_id,
                telegram_payment_charge_id=sp.telegram_payment_charge_id,
                provider_payment_charge_id=sp.provider_payment_charge_id,
                amount_tiyin=sp.total_amount,
                currency=sp.currency,
            )
        )

        now = datetime.utcnow()
        stmt = (
            pg_insert(BotUser)
            .values(telegram_user_id=user_id, subscription_until=now)
            .on_conflict_do_nothing(index_elements=[BotUser.telegram_user_id])
        )
        await db.execute(stmt)
        user = await db.get(BotUser, user_id)
        base = user.subscription_until if user.subscription_until and user.subscription_until > now else now
        user.subscription_until = base + timedelta(days=settings.subscription_days)

        await db.commit()

    await message.answer(
        "✅ Obuna faollashtirildi! Endi kunlik limitsiz chek skanerlashingiz mumkin."
    )


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
