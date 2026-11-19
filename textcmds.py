"""Текстовые аналоги действий, которые в личке делаются кнопками (для групп и для лички)."""
from aiogram import Bot
from aiogram.filters import CommandObject
from aiogram.types import Message

import database as dbm
import extra_handlers as ex
import game
import user_handlers as uh
from game_data import *
from matching import find_items, find_crop, norm
from utils import fmt, fmt_f

KIND_WORDS = {
    "бизнес": "biz", "бизнесы": "biz",
    "майнеры": "miner", "майнер": "miner", "ферма": "miner",
    "недвижимость": "realty",
}


def _title(kind, key):
    it = DATA[kind][key]
    return f"{it['emoji']} {it['name']}"


# ---------- кирка ----------
async def upgrade_pickaxe(user):
    lvl = user["pickaxe"]
    if lvl >= MAX_PICKAXE:
        return "✅ Кирка уже максимального уровня"
    cost = pickaxe_cost(lvl)
    if not await dbm.spend(user["id"], cost):
        return f"❌ Не хватает {fmt(cost - user['balance'])} $ (улучшение стоит {fmt(cost)} $)"
    await dbm.execute("UPDATE users SET pickaxe=pickaxe+1 WHERE id=?", (user["id"],))
    return f"🔨 Кирка улучшена до ур. {lvl + 1}!"


async def h_pickaxe(m: Message, user: dict):
    lvl = user["pickaxe"]
    lo, hi = mine_range(lvl)
    text = f"🔨 Кирка: ур. {lvl}/{MAX_PICKAXE} ({lo}–{hi} $ за удар)"
    if lvl < MAX_PICKAXE:
        text += f"\nУлучшение: {fmt(pickaxe_cost(lvl))} $ — напиши «улучшить кирку»"
    await m.answer(text)


# ---------- купить / улучшить ----------
async def _buy(m, user, arg):
    if not arg:
        return await m.answer("Напиши, что купить: «купить кофейня», «купить квартира», «купить видеокарта».\n"
                              "Списки: «бизнес», «майнеры», «недвижимость».")
    found = find_items(arg)
    if not found:
        return await m.answer("❌ Не нашёл такой объект. Списки: «бизнес», «майнеры», «недвижимость».")
    if len(found) > 1:
        names = ", ".join(DATA[k][key]["name"] for k, key in found)
        return await m.answer(f"Уточни, что именно: {names}")
    kind, key = found[0]
    notice = await uh.do_buy(user["id"], kind, key)
    await m.answer(f"{_title(kind, key)}: {notice}")


async def h_buy(m: Message, user: dict, command: CommandObject):
    await _buy(m, user, command.args)


async def h_upgrade(m: Message, user: dict, command: CommandObject):
    arg = norm(command.args)
    if arg.startswith("кирк"):
        return await m.answer(await upgrade_pickaxe(user))
    await _buy(m, user, command.args)


# ---------- продать ----------
async def sell_skr(uid):
    u = await dbm.get_user(uid)
    rate = await dbm.get_rate()
    money = int(u["skr"] * rate)
    if money <= 0:
        return "❌ Нет SKR для продажи"
    await dbm.execute("UPDATE users SET skr=0 WHERE id=?", (uid,))
    await dbm.add_balance(uid, money)
    return f"💱 Продано {fmt_f(u['skr'])} SKR за {fmt(money)} $"


async def h_sell(m: Message, user: dict, command: CommandObject):
    arg = norm(command.args)
    if arg in ("скр", "skr", "sk", "крипту", "крипта", "монеты", "все скр", "всё скр"):
        return await m.answer(await sell_skr(user["id"]))
    found = [f for f in find_items(arg) if f[0] == "realty"] if arg else []
    if not found:
        return await m.answer("Использование: «продать квартира» (недвижимость) или «продать скр»")
    if len(found) > 1:
        return await m.answer("Уточни название объекта")
    kind, key = found[0]
    await m.answer(f"{_title(kind, key)}: {await uh.do_sell_realty(user['id'], key)}")


# ---------- собрать ----------
async def h_collect(m: Message, user: dict, command: CommandObject):
    a = norm(command.args)
    if a in ("огород", "урожай", "грядки"):
        return await m.answer(await ex.garden_harvest(user["id"]))
    if a in ("вклад", "депозит", "банк"):
        return await m.answer(await ex.bank_take(user["id"], early=False))
    if a and a not in KIND_WORDS and a not in ("все", "всё"):
        return await m.answer("Что собрать? «собрать бизнес», «собрать майнеры», «собрать недвижимость», «урожай»")
    kinds = [KIND_WORDS[a]] if a in KIND_WORDS else ["biz", "miner", "realty"]
    lines = []
    for kind in kinds:
        amt = await game.collect_kind(user, kind)
        if kind == "miner":
            if amt > 0:
                lines.append(f"🖥 Майнеры: +{fmt_f(amt)} SKR")
        elif amt > 0:
            lines.append(f"{'🏢 Бизнесы' if kind == 'biz' else '🏠 Недвижимость'}: +{fmt(amt)} $")
    await m.answer("💰 Собрано:\n" + "\n".join(lines) if lines else "Пока нечего собирать")


# ---------- огород ----------
async def h_plant(m: Message, user: dict, command: CommandObject):
    key = find_crop(command.args)
    if not key:
        crops = ", ".join(c["name"].lower() for c in CROPS.values())
        return await m.answer(f"Что посадить? Например: «посадить морковь». Доступно: {crops}")
    await m.answer(await ex.garden_plant(user["id"], key))


async def h_harvest(m: Message, user: dict):
    await m.answer(await ex.garden_harvest(user["id"]))


# ---------- вклад ----------
async def h_bank_take(m: Message, user: dict):
    await m.answer(await ex.bank_take(user["id"], early=False))


async def h_early(m: Message, user: dict):
    await m.answer(await ex.bank_take(user["id"], early=True))


# ---------- премиум ----------
async def h_paid(m: Message, user: dict, bot: Bot):
    ok, msg = await uh.submit_premium_request(user, bot)
    await m.answer(msg)
