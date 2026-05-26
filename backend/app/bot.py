from aiogram import Bot, Dispatcher
from aiogram.types import MenuButtonWebApp, Update, WebAppInfo
from aiogram.filters import CommandStart
from aiogram import Router
from aiogram.types import Message

from app.config import settings

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
    await message.answer(
        "Tap the menu button below to open the bill splitter.",
    )


async def process_update(update_data: dict):
    update = Update(**update_data)
    await dp.feed_update(bot, update)
