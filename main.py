"""Entry point: python main.py (needs BOT_TOKEN in the environment)."""
import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from kickoff.bot import handlers
from kickoff.config import Config
from kickoff.storage import Storage


async def main() -> None:
    logging.basicConfig(level=Config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not Config.token:
        sys.exit("BOT_TOKEN is not set. Put the token from @BotFather into the BOT_TOKEN environment variable.")
    os.makedirs(os.path.dirname(Config.db_path) or ".", exist_ok=True)
    storage = Storage(Config.db_path)
    bot = Bot(Config.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(handlers.setup(storage))
    await bot.set_my_commands([
        BotCommand(command="menu", description="Головне меню"),
        BotCommand(command="help", description="Як грати"),
        BotCommand(command="top", description="Зала слави"),
        BotCommand(command="new", description="Нова кар’єра"),
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
