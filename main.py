import asyncio
import logging
import random

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import admin_handlers
import aliases
import extra_handlers
import database as dbm
import user_handlers
from config import BOT_TOKEN
from game_data import (
    SKR_RATE_MIN, SKR_RATE_MAX, SKR_RATE_TARGET, SKR_UPDATE_SECONDS,
)
from middlewares import MainMiddleware


async def rate_updater():
    """Раз в SKR_UPDATE_SECONDS меняет курс SKR (случайное блуждание с возвратом к среднему)."""
    while True:
        try:
            rate = await dbm.get_rate()
            drift = (SKR_RATE_TARGET - rate) * 0.05
            new = rate * random.uniform(0.93, 1.07) + drift
            new = min(max(new, SKR_RATE_MIN), SKR_RATE_MAX)
            await dbm.set_setting("skr_rate_prev", f"{rate:.2f}")
            await dbm.set_setting("skr_rate", f"{new:.2f}")
        except Exception:
            logging.exception("rate_updater error")
        await asyncio.sleep(SKR_UPDATE_SECONDS)


async def main():
    logging.basicConfig(level=logging.INFO)
    await dbm.init()

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    mw = MainMiddleware()
    dp.message.outer_middleware(mw)
    dp.callback_query.outer_middleware(mw)

    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)
    dp.include_router(extra_handlers.router)
    dp.include_router(aliases.router)  # текстовые команды без «/» — всегда последним

    task = asyncio.create_task(rate_updater())
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        task.cancel()
        await dbm.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
