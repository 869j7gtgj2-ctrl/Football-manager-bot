"""Entry point: runs the Telegram bot (polling) and the Mini App web server in one process."""
import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo
from aiohttp import web

from kickoff import realdata
from kickoff.bot import handlers
from kickoff.config import Config
from kickoff.service import Service
from kickoff.storage import Storage
from kickoff.web.server import create_app

log = logging.getLogger("kickoff")


async def main() -> None:
    logging.basicConfig(level=Config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    os.makedirs(os.path.dirname(Config.db_path) or ".", exist_ok=True)
    storage = Storage(Config.db_path)
    svc = Service(storage)

    # web server (Mini App + API)
    app = create_app(svc, Config.token)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", Config.port).start()
    log.info("Web server on port %s, Mini App URL: %s", Config.port, Config.webapp_url)

    # real squads / crests refresh in the background
    asyncio.create_task(realdata.refresh_loop(storage, Config.football_data_key))

    if not Config.token:
        log.error("BOT_TOKEN is not set: only the web server is running.")
        await asyncio.Event().wait()
    bot = Bot(Config.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(handlers.setup(storage, Config.webapp_url))
    await bot.set_my_commands([
        BotCommand(command="start", description="Грати"),
        BotCommand(command="top", description="Зала слави"),
    ])
    if Config.webapp_url:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Грати", web_app=WebAppInfo(url=Config.webapp_url)))
    else:
        log.warning("No public domain: set RAILWAY_PUBLIC_DOMAIN (Generate Domain in Railway) or WEBAPP_URL.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
