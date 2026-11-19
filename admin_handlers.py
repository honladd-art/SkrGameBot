import asyncio
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery

import database as dbm
import game
from config import ADMIN_SET, PREMIUM_DAYS
from game_data import SKR_RATE_MIN, SKR_RATE_MAX
from utils import fmt, fmt_f, esc, short_name, is_premium, badges

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_SET))
router.callback_query.filter(F.from_user.id.in_(ADMIN_SET))

ADMIN_HELP = (
    "🛠 <b>Админ-команды</b>\n\n"
    "/stats — статистика бота\n"
    "/user [ID|@ник] — информация об игроке\n"
    "/give [ID|@ник] [сумма] — выдать деньги\n"
    "/take [ID|@ник] [сумма] — забрать деньги\n"
    "/setbal [ID|@ник] [сумма] — установить баланс\n"
    "/givesk [ID|@ник] [кол-во] — выдать SKR\n"
    "/addprem [ID|@ник] [дней] — выдать премиум\n"
    "/delprem [ID|@ник] — снять премиум\n"
    "/ban [ID|@ник] — заблокировать\n"
    "/unban [ID|@ник] — разблокировать\n"
    "/resetuser [ID|@ник] — полностью сбросить прогресс\n"
    "/newpromo [КОД] [сумма] [активаций] — создать промокод\n"
    "/delpromo [КОД] — удалить промокод\n"
    "/promos — список промокодов\n"
    "/setrate [курс] — установить курс SKR\n"
    "/requests — заявки на премиум\n"
    "/broadcast [текст] — рассылка всем игрокам"
)


async def get_target(m: Message, args, idx=0):
    """Возвращает игрока по аргументу или None (сообщив об ошибке)."""
    if len(args) <= idx:
        await m.answer("❌ Укажите игрока (ID или @ник)")
        return None
    u = await dbm.find_user(args[idx])
    if u is None:
        await m.answer("❌ Игрок не найден")
    return u


def parse_int(s):
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


@router.message(Command("admin"))
async def a_help(m: Message):
    await m.answer(ADMIN_HELP)


@router.message(Command("stats"))
async def a_stats(m: Message):
    total = await dbm.fetchone("SELECT COUNT(*) AS n, COALESCE(SUM(balance),0) AS bal, COALESCE(SUM(skr),0) AS skr FROM users")
    prem = await dbm.fetchone("SELECT COUNT(*) AS n FROM users WHERE premium_until>strftime('%s','now')")
    banned = await dbm.fetchone("SELECT COUNT(*) AS n FROM users WHERE banned=1")
    pending = await dbm.fetchone("SELECT COUNT(*) AS n FROM premium_requests WHERE status='pending'")
    day = await dbm.fetchone("SELECT COUNT(*) AS n FROM users WHERE created>strftime('%s','now')-86400")
    assets = await dbm.fetchone("SELECT COUNT(*) AS n FROM assets")
    rate = await dbm.get_rate()
    await m.answer(
        "📊 <b>Статистика</b>\n\n"
        f"👥 Игроков: {fmt(total['n'])} (+{day['n']} за 24 ч)\n"
        f"💎 Премиум: {prem['n']}\n"
        f"🚫 Забанено: {banned['n']}\n"
        f"💰 Денег в игре: {fmt(total['bal'])} $\n"
        f"🪙 SKR в игре: {fmt_f(total['skr'])}\n"
        f"🏢 Активов: {fmt(assets['n'])}\n"
        f"📈 Курс SKR: {fmt_f(rate)} $\n"
        f"📨 Заявок на премиум: {pending['n']}"
    )


@router.message(Command("user"))
async def a_user(m: Message, command: CommandObject):
    args = (command.args or "").split()
    u = await get_target(m, args)
    if not u:
        return
    assets = await dbm.get_assets(u["id"])
    rate = await dbm.get_rate()
    worth = u["balance"] + u["skr"] * rate
    prem = datetime.fromtimestamp(u["premium_until"]).strftime("%d.%m.%Y %H:%M") if is_premium(u) else "нет"
    created = datetime.fromtimestamp(u["created"]).strftime("%d.%m.%Y %H:%M")
    uname = f"@{u['username']}" if u["username"] else "—"
    lst = ", ".join(f"{a['kind']}:{a['item']}×{a['qty'] if a['kind'] != 'biz' else a['level']}" for a in assets) or "—"
    await m.answer(
        f"👤 <b>{badges(u)} {short_name(u)}</b> ({uname})\n"
        f"🆔 <code>{u['id']}</code>\n"
        f"💰 {fmt(u['balance'])} $ · 🪙 {fmt_f(u['skr'])} SKR\n"
        f"🏦 Состояние: {fmt(worth)} $\n"
        f"🔨 Кирка: {u['pickaxe']} · ударов: {fmt(u['mined'])}\n"
        f"💎 Премиум: {prem}\n"
        f"👥 Рефералов: {u['refs']} · пригласил: {u['ref_by'] or '—'}\n"
        f"🚫 Бан: {'да' if u['banned'] else 'нет'}\n"
        f"📅 Регистрация: {created}\n"
        f"📦 Активы: {esc(lst)}"
    )


@router.message(Command("give"))
async def a_give(m: Message, command: CommandObject, bot: Bot):
    args = (command.args or "").split()
    u = await get_target(m, args)
    amount = parse_int(args[1]) if len(args) > 1 else None
    if not u or not amount or amount <= 0:
        return await m.answer("Использование: /give [ID|@ник] [сумма]") if u else None
    await dbm.add_balance(u["id"], amount)
    await m.answer(f"✅ Выдано {fmt(amount)} $ → {short_name(u)}")
    try:
        await bot.send_message(u["id"], f"🎁 Администратор выдал вам <b>{fmt(amount)} $</b>")
    except Exception:
        pass


@router.message(Command("take"))
async def a_take(m: Message, command: CommandObject):
    args = (command.args or "").split()
    u = await get_target(m, args)
    amount = parse_int(args[1]) if len(args) > 1 else None
    if not u or not amount or amount <= 0:
        return await m.answer("Использование: /take [ID|@ник] [сумма]") if u else None
    await dbm.execute("UPDATE users SET balance=MAX(0, balance-?) WHERE id=?", (amount, u["id"]))
    await m.answer(f"✅ Списано до {fmt(amount)} $ у {short_name(u)}")


@router.message(Command("setbal"))
async def a_setbal(m: Message, command: CommandObject):
    args = (command.args or "").split()
    u = await get_target(m, args)
    amount = parse_int(args[1]) if len(args) > 1 else None
    if not u or amount is None or amount < 0:
        return await m.answer("Использование: /setbal [ID|@ник] [сумма]") if u else None
    await dbm.execute("UPDATE users SET balance=? WHERE id=?", (amount, u["id"]))
    await m.answer(f"✅ Баланс {short_name(u)} = {fmt(amount)} $")


@router.message(Command("givesk"))
async def a_givesk(m: Message, command: CommandObject):
    args = (command.args or "").split()
    u = await get_target(m, args)
    try:
        amount = float(args[1])
    except (IndexError, ValueError):
        amount = None
    if not u or amount is None:
        return await m.answer("Использование: /givesk [ID|@ник] [кол-во]") if u else None
    await dbm.execute("UPDATE users SET skr=MAX(0, skr+?) WHERE id=?", (amount, u["id"]))
    await m.answer(f"✅ {fmt_f(amount)} SKR → {short_name(u)}")


@router.message(Command("addprem"))
async def a_addprem(m: Message, command: CommandObject, bot: Bot):
    args = (command.args or "").split()
    u = await get_target(m, args)
    if not u:
        return
    days = parse_int(args[1]) if len(args) > 1 else PREMIUM_DAYS
    if not days or days <= 0:
        return await m.answer("❌ Неверное количество дней")
    until = await dbm.give_premium(u["id"], days)
    await m.answer(f"💎 Премиум для {short_name(u)} до {datetime.fromtimestamp(until).strftime('%d.%m.%Y %H:%M')}")
    try:
        await bot.send_message(u["id"], f"💎 Вам выдан премиум на {days} дн.! Спасибо за поддержку!")
    except Exception:
        pass


@router.message(Command("delprem"))
async def a_delprem(m: Message, command: CommandObject):
    u = await get_target(m, (command.args or "").split())
    if not u:
        return
    await dbm.execute("UPDATE users SET premium_until=0 WHERE id=?", (u["id"],))
    await m.answer(f"✅ Премиум снят у {short_name(u)}")


@router.message(Command("ban"))
async def a_ban(m: Message, command: CommandObject):
    u = await get_target(m, (command.args or "").split())
    if not u:
        return
    if u["id"] in ADMIN_SET:
        return await m.answer("❌ Нельзя заблокировать администратора")
    await dbm.execute("UPDATE users SET banned=1 WHERE id=?", (u["id"],))
    await m.answer(f"🚫 {short_name(u)} заблокирован")


@router.message(Command("unban"))
async def a_unban(m: Message, command: CommandObject):
    u = await get_target(m, (command.args or "").split())
    if not u:
        return
    await dbm.execute("UPDATE users SET banned=0 WHERE id=?", (u["id"],))
    await m.answer(f"✅ {short_name(u)} разблокирован")


@router.message(Command("resetuser"))
async def a_reset(m: Message, command: CommandObject):
    u = await get_target(m, (command.args or "").split())
    if not u:
        return
    await dbm.execute("DELETE FROM assets WHERE user_id=?", (u["id"],))
    for table in ("farm", "deposits", "cd"):
        await dbm.execute(f"DELETE FROM {table} WHERE user_id=?", (u["id"],))
    await dbm.execute(
        "UPDATE users SET balance=0, skr=0, pickaxe=1, mined=0, last_mine=0, last_work=0, "
        "last_bonus=0, streak=0 WHERE id=?", (u["id"],)
    )
    await m.answer(f"♻️ Прогресс {short_name(u)} сброшен (премиум и бан сохранены)")


# ---------- промокоды ----------
@router.message(Command("newpromo"))
async def a_newpromo(m: Message, command: CommandObject):
    args = (command.args or "").split()
    amount = parse_int(args[1]) if len(args) > 1 else None
    uses = parse_int(args[2]) if len(args) > 2 else None
    if len(args) < 3 or not amount or amount <= 0 or not uses or uses <= 0:
        return await m.answer("Использование: /newpromo [КОД] [сумма] [активаций]")
    code = args[0].upper()
    await dbm.execute(
        "INSERT INTO promos(code, amount, uses) VALUES(?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET amount=excluded.amount, uses=excluded.uses",
        (code, amount, uses),
    )
    await m.answer(f"🎟 Промокод <code>{esc(code)}</code>: {fmt(amount)} $, активаций: {uses}")


@router.message(Command("delpromo"))
async def a_delpromo(m: Message, command: CommandObject):
    code = (command.args or "").strip().upper()
    if not code:
        return await m.answer("Использование: /delpromo [КОД]")
    n = await dbm.execute("DELETE FROM promos WHERE code=?", (code,))
    await m.answer("✅ Удалён" if n else "❌ Не найден")


@router.message(Command("promos"))
async def a_promos(m: Message):
    rows = await dbm.fetchall("SELECT * FROM promos")
    if not rows:
        return await m.answer("Промокодов нет")
    await m.answer("🎟 <b>Промокоды</b>\n" + "\n".join(
        f"<code>{esc(r['code'])}</code> — {fmt(r['amount'])} $, осталось {r['uses']}" for r in rows
    ))


# ---------- курс ----------
@router.message(Command("setrate"))
async def a_setrate(m: Message, command: CommandObject):
    try:
        rate = float((command.args or "").replace(",", "."))
    except ValueError:
        return await m.answer(f"Использование: /setrate [курс] ({SKR_RATE_MIN:g}–{SKR_RATE_MAX:g})")
    rate = min(max(rate, SKR_RATE_MIN), SKR_RATE_MAX)
    await dbm.set_setting("skr_rate_prev", await dbm.get_rate())
    await dbm.set_setting("skr_rate", f"{rate:.2f}")
    await m.answer(f"📈 Курс SKR = {rate:.2f} $")


# ---------- премиум-заявки ----------
@router.message(Command("requests"))
async def a_requests(m: Message):
    rows = await dbm.fetchall("SELECT * FROM premium_requests WHERE status='pending'")
    if not rows:
        return await m.answer("Нет активных заявок")
    from user_handlers import btn, ikb  # локальный импорт, чтобы не создавать цикл
    for r in rows:
        u = await dbm.get_user(r["user_id"])
        uname = f"@{u['username']}" if u and u["username"] else "без username"
        await m.answer(
            f"💎 Заявка #{r['id']}\n{short_name(u) if u else '?'} ({uname})\nID: <code>{r['user_id']}</code>",
            reply_markup=ikb([[btn("✅ Выдать", f"pa:ok:{r['id']}"), btn("❌ Отклонить", f"pa:no:{r['id']}")]]),
        )


@router.callback_query(F.data.startswith("pa:"))
async def cb_prem_decision(c: CallbackQuery, bot: Bot):
    _, act, rid = c.data.split(":")
    rid = int(rid)
    new_status = "approved" if act == "ok" else "rejected"
    n = await dbm.execute(
        "UPDATE premium_requests SET status=? WHERE id=? AND status='pending'", (new_status, rid)
    )
    if n == 0:
        return await c.answer("Заявка уже обработана", show_alert=True)
    req = await dbm.fetchone("SELECT * FROM premium_requests WHERE id=?", (rid,))
    admin_name = esc(c.from_user.full_name)
    if act == "ok":
        until = await dbm.give_premium(req["user_id"], PREMIUM_DAYS)
        mark = f"\n\n✅ Одобрено — {admin_name}"
        msg = f"💎 Премиум активирован до {datetime.fromtimestamp(until).strftime('%d.%m.%Y %H:%M')}! Спасибо за поддержку ❤️"
    else:
        mark = f"\n\n❌ Отклонено — {admin_name}"
        msg = "❌ Заявка на премиум отклонена. Оплата не найдена — напишите администратору."
    try:
        await c.message.edit_text((c.message.html_text or "") + mark)
    except Exception:
        pass
    try:
        await bot.send_message(req["user_id"], msg)
    except Exception:
        pass
    await c.answer("Готово")


# ---------- рассылка ----------
@router.message(Command("broadcast"))
async def a_broadcast(m: Message, command: CommandObject, bot: Bot):
    text = (command.args or "").strip()
    if not text:
        return await m.answer("Использование: /broadcast [текст] (поддерживается HTML)")
    users = await dbm.fetchall("SELECT id FROM users WHERE banned=0")
    await m.answer(f"📨 Рассылка запущена: {len(users)} получателей...")
    ok = fail = 0
    for u in users:
        try:
            await bot.send_message(u["id"], f"📢 {text}")
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await m.answer(f"✅ Рассылка завершена\nДоставлено: {ok}\nОшибок: {fail}")
