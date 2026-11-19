import asyncio
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

import database as dbm


class MainMiddleware(BaseMiddleware):
    """Регистрирует игрока, проверяет бан и обрабатывает действия одного игрока по очереди
    (защита от дублей при спаме кнопок)."""

    def __init__(self):
        self.locks = defaultdict(asyncio.Lock)

    async def __call__(self, handler, event, data):
        tg = data.get("event_from_user")
        if tg is None or tg.is_bot:
            return await handler(event, data)

        if isinstance(event, Message) and event.chat.type != "private":
            return  # бот работает только в личке

        async with self.locks[tg.id]:
            ref = None
            if isinstance(event, Message) and event.text and event.text.startswith("/start"):
                parts = event.text.split()
                if len(parts) > 1 and parts[1].startswith("ref_") and parts[1][4:].isdigit():
                    ref = int(parts[1][4:])

            user = await dbm.upsert_user(tg, ref)

            if user["banned"]:
                if isinstance(event, CallbackQuery):
                    await event.answer("🚫 Вы заблокированы", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer("🚫 Вы заблокированы.")
                return

            data["user"] = user
            return await handler(event, data)
