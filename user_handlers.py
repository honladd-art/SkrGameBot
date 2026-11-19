import random
import time
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import database as dbm
import game
from config import (
    ADMIN_SET, PREMIUM_CONTACT, PREMIUM_PRICE_RUB, PREMIUM_PRICE_STARS, PREMIUM_DAYS,
)
from game_data import *
from utils import fmt, fmt_f, esc, short_name, is_premium, badges, fmt_dur

router = Router()

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⛏ Шахта"), KeyboardButton(text="💼 Работа")],
        [KeyboardButton(text="🏢 Бизнесы"), KeyboardButton(text="🖥 Майнеры"), KeyboardButton(text="🏠 Недвижимость")],
        [KeyboardButton(text="🎣 Рыбалка"), KeyboardButton(text="🌱 Огород"), KeyboardButton(text="🏦 Банк")],
        [KeyboardButton(text="🎁 Бонус"), KeyboardButton(text="🎰 Казино"), KeyboardButton(text="🏆 Топ")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💎 Премиум"), KeyboardButton(text="❓ Помощь")],
    ],
    resize_keyboard=True,
)

_me = None


async def bot_username(bot: Bot):
    global _me
    if _me is None:
        _me = (await bot.get_me()).username
    return _me


def btn(text, data=None, url=None):
    return InlineKeyboardButton(text=text, callback_data=data, url=url)


def ikb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def safe_edit(c: CallbackQuery, text, kb=None):
    try:
        await c.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass


# ======================= СТАРТ / ПОМОЩЬ =======================
@router.message(Command("start"))
async def h_start(m: Message, user: dict):
    await m.answer(
        f"👋 Привет, <b>{short_name(user)}</b>! Это <b>SkrGame</b> — экономическая игра.\n\n"
        "С чего начать:\n"
        "1️⃣ Копай шахту ⛏ и набери 500 $\n"
        "2️⃣ Купи первый бизнес 🏢 и улучшай его\n"
        "3️⃣ Покупай майнеры 🖥 и недвижимость 🏠\n"
        "4️⃣ Попади в топ 🏆\n\n"
        "Все команды — в ❓ Помощь.",
        reply_markup=MENU,
    )


HELP_TEXT = (
    "❓ <b>Помощь</b>\n\n"
    "⛏ /mine — копать шахту, улучшать кирку\n"
    "💼 /work — подработка (раз в час)\n"
    "🎣 /fish — рыбалка (раз в 5 мин)\n"
    "🌱 /garden — огород: сажай и собирай урожай\n"
    "🏦 /bank — вклад под процент (/deposit сумма)\n"
    "🏢 /business — бизнесы\n"
    "🖥 /miners — майнеры (SKR)\n"
    "🏠 /realty — недвижимость\n"
    "🎁 /bonus — ежедневный бонус\n"
    "🎰 /casino [ставка] — казино\n"
    "💸 /pay [@ник|ID] [сумма] — перевод (или ответом на сообщение: /pay сумма)\n"
    "🎟 /promo [код] — промокод\n"
    "🏆 /top — рейтинг\n"
    "👤 /profile — профиль и реф. ссылка\n"
    "💎 /premium — премиум\n\n"
    "💬 Команды работают и словами без «/»:\n"
    "шахта, работа, бизнес, майнеры, недвижимость, рыбалка, огород, банк, бонус, "
    "казино 1000, перевод @ник 500, промо КОД, топ, профиль, премиум"
)


@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def h_help(m: Message, user: dict):
    await m.answer(HELP_TEXT, reply_markup=MENU)


# ======================= ШАХТА =======================
def mine_text(u, header=""):
    lvl = u["pickaxe"]
    lo, hi = mine_range(lvl)
    text = (
        f"⛏ <b>Шахта</b>\n{header}"
        f"💰 Баланс: <b>{fmt(u['balance'])} $</b>\n"
        f"🔨 Кирка: ур. {lvl}/{MAX_PICKAXE} ({lo}–{hi} $ за удар)\n"
        f"⛏ Всего ударов: {fmt(u['mined'])}"
    )
    if u["balance"] < 500:
        text += "\n\n💡 Набери 500 $, чтобы купить первый бизнес 🏢"
    rows = [[btn("⛏ Копать", "mine:dig")]]
    if lvl < MAX_PICKAXE:
        rows.append([btn(f"🔧 Улучшить кирку · {fmt(pickaxe_cost(lvl))} $", "mine:up")])
    return text, ikb(rows)


async def do_mine(user):
    now = time.time()
    left = MINE_COOLDOWN - (now - user["last_mine"])
    if left > 0:
        return False, f"⏳ Кирка остывает: {left:.0f} сек.", None
    lo, hi = mine_range(user["pickaxe"])
    gain = random.randint(lo, hi)
    header = ""
    if random.random() < 0.05:
        gain *= 10
        header = "💎 Нашёл самородок! x10\n"
    if is_premium(user):
        gain = int(gain * PREMIUM_MINE_MULT)
    await dbm.execute(
        "UPDATE users SET balance=balance+?, mined=mined+1, last_mine=? WHERE id=?",
        (gain, now, user["id"]),
    )
    u = await dbm.get_user(user["id"])
    text, kb = mine_text(u, f"{header}➕ <b>{fmt(gain)} $</b>\n")
    return True, text, kb


@router.message(Command("mine"))
@router.message(F.text == "⛏ Шахта")
async def h_mine(m: Message, user: dict):
    ok, text, kb = await do_mine(user)
    if ok:
        await m.answer(text, reply_markup=kb)
    else:
        t, k = mine_text(user, f"{text}\n")
        await m.answer(t, reply_markup=k)


@router.callback_query(F.data == "mine:dig")
async def cb_dig(c: CallbackQuery, user: dict):
    ok, text, kb = await do_mine(user)
    if not ok:
        return await c.answer(text)
    await safe_edit(c, text, kb)
    await c.answer()


@router.callback_query(F.data == "mine:up")
async def cb_pick_up(c: CallbackQuery, user: dict):
    lvl = user["pickaxe"]
    if lvl >= MAX_PICKAXE:
        return await c.answer("Максимальный уровень!")
    cost = pickaxe_cost(lvl)
    if not await dbm.spend(user["id"], cost):
        return await c.answer(f"❌ Не хватает {fmt(cost - user['balance'])} $", show_alert=True)
    await dbm.execute("UPDATE users SET pickaxe=pickaxe+1 WHERE id=?", (user["id"],))
    u = await dbm.get_user(user["id"])
    text, kb = mine_text(u, f"✅ Кирка улучшена до ур. {u['pickaxe']}!\n")
    await safe_edit(c, text, kb)
    await c.answer()


# ======================= РАЗДЕЛЫ: БИЗНЕС / МАЙНЕРЫ / НЕДВИЖИМОСТЬ =======================
async def render_section(kind, uid):
    u = await dbm.get_user(uid)
    assets = {a["item"]: a for a in await dbm.get_assets(uid, kind)}
    now = time.time()
    pend = sum(game.pending_amount(u, kind, a, now) for a in assets.values())
    hours = PREMIUM_STORAGE_HOURS if is_premium(u) else STORAGE_HOURS
    lines, rows = [], []

    if kind == "biz":
        lines.append("🏢 <b>Бизнесы</b>\n")
        for key, b in BUSINESSES.items():
            a = assets.get(key)
            if a:
                lvl = a["level"]
                lines.append(f"{b['emoji']} <b>{b['name']}</b> · ур. {lvl}/{MAX_BIZ_LEVEL} · {fmt(biz_income(key, lvl))} $/ч")
                if lvl < MAX_BIZ_LEVEL:
                    rows.append([btn(f"⬆️ {b['name']} → ур. {lvl + 1} · {fmt(biz_upgrade_cost(key, lvl))} $", f"sec:biz:buy:{key}")])
            else:
                lines.append(f"🔒 {b['emoji']} {b['name']} · {fmt(b['cost'])} $ · {fmt(b['income'])} $/ч")
                rows.append([btn(f"🛒 {b['name']} · {fmt(b['cost'])} $", f"sec:biz:buy:{key}")])
        lines.append(f"\n💵 Накоплено: <b>{fmt(pend)} $</b> (хранилище {hours} ч)")
        if assets:
            rows.append([btn(f"💰 Собрать +{fmt(pend)} $", "sec:biz:collect")])

    elif kind == "miner":
        rate = await dbm.get_rate()
        prev = await dbm.get_prev_rate()
        arrow = "📈" if rate > prev else ("📉" if rate < prev else "➖")
        lines.append("🖥 <b>Майнеры</b> — добывают SKR\n")
        lines.append(f"{arrow} Курс: <b>{fmt_f(rate)} $</b> за 1 SKR (обновляется каждые {SKR_UPDATE_SECONDS // 60} мин)\n")
        for key, b in MINERS.items():
            a = assets.get(key)
            qty = a["qty"] if a else 0
            if qty:
                lines.append(f"{b['emoji']} <b>{b['name']}</b> × {qty}/{MAX_QTY} · {fmt(b['yield'] * qty)} SKR/ч")
            else:
                lines.append(f"🔒 {b['emoji']} {b['name']} · {fmt(b['cost'])} $ · {fmt(b['yield'])} SKR/ч")
            if qty < MAX_QTY:
                rows.append([btn(f"🛒 {b['name']} · {fmt(unit_cost(b['cost'], qty))} $", f"sec:miner:buy:{key}")])
        lines.append(f"\n⛏ Накоплено: <b>{fmt_f(pend)} SKR</b> (хранилище {hours} ч)")
        lines.append(f"🪙 На счёте: <b>{fmt_f(u['skr'])} SKR</b> ≈ {fmt(u['skr'] * rate)} $")
        if assets:
            rows.append([btn(f"⛏ Собрать +{fmt_f(pend)} SKR", "sec:miner:collect")])
        if u["skr"] > 0:
            rows.append([btn(f"💱 Продать SKR · +{fmt(u['skr'] * rate)} $", "sec:miner:sellskr")])

    else:
        lines.append("🏠 <b>Недвижимость</b> — пассивная аренда\n")
        for key, b in REALTY.items():
            a = assets.get(key)
            qty = a["qty"] if a else 0
            if qty:
                lines.append(f"{b['emoji']} <b>{b['name']}</b> × {qty}/{MAX_QTY} · {fmt(b['rent'] * qty)} $/ч")
            else:
                lines.append(f"🔒 {b['emoji']} {b['name']} · {fmt(b['cost'])} $ · {fmt(b['rent'])} $/ч")
            row = []
            if qty < MAX_QTY:
                row.append(btn(f"🛒 {b['name']} · {fmt(unit_cost(b['cost'], qty))} $", f"sec:realty:buy:{key}"))
            if qty > 0:
                refund = int(unit_cost(b["cost"], qty - 1) * REALTY_SELL_RATIO)
                row.append(btn(f"💸 +{fmt(refund)} $", f"sec:realty:sell:{key}"))
            if row:
                rows.append(row)
        lines.append(f"\n💵 Накоплено: <b>{fmt(pend)} $</b> (хранилище {hours} ч)")
        lines.append(f"💸 Продажа 1 шт. возвращает {int(REALTY_SELL_RATIO * 100)}% цены")
        if assets:
            rows.append([btn(f"💰 Собрать +{fmt(pend)} $", "sec:realty:collect")])

    lines.append(f"\n💰 Баланс: <b>{fmt(u['balance'])} $</b>")
    return "\n".join(lines), ikb(rows)


async def do_buy(uid, kind, key):
    data = DATA[kind]
    if key not in data:
        return "❌ Не найдено"
    u = await dbm.get_user(uid)
    await game.collect_kind(u, kind)  # сначала забираем накопленное
    u = await dbm.get_user(uid)
    a = await dbm.get_asset(uid, kind, key)
    item = data[key]

    if kind == "biz":
        if a is None:
            cost = item["cost"]
        elif a["level"] >= MAX_BIZ_LEVEL:
            return "✅ Максимальный уровень"
        else:
            cost = biz_upgrade_cost(key, a["level"])
    else:
        qty = a["qty"] if a else 0
        if qty >= MAX_QTY:
            return f"❌ Максимум {MAX_QTY} шт."
        cost = unit_cost(item["cost"], qty)

    if not await dbm.spend(uid, cost):
        return f"❌ Не хватает {fmt(cost - u['balance'])} $"

    if a is None:
        await dbm.add_asset(uid, kind, key, time.time())
        return "✅ Куплено!"
    if kind == "biz":
        await dbm.execute("UPDATE assets SET level=level+1 WHERE user_id=? AND kind=? AND item=?", (uid, kind, key))
        return f"✅ Улучшено до ур. {a['level'] + 1}!"
    await dbm.execute("UPDATE assets SET qty=qty+1 WHERE user_id=? AND kind=? AND item=?", (uid, kind, key))
    return "✅ Куплено!"


async def do_sell_realty(uid, key):
    if key not in REALTY:
        return "❌ Не найдено"
    u = await dbm.get_user(uid)
    await game.collect_kind(u, "realty")
    a = await dbm.get_asset(uid, "realty", key)
    if not a or a["qty"] < 1:
        return "❌ Нечего продавать"
    refund = int(unit_cost(REALTY[key]["cost"], a["qty"] - 1) * REALTY_SELL_RATIO)
    if a["qty"] == 1:
        await dbm.execute("DELETE FROM assets WHERE user_id=? AND kind='realty' AND item=?", (uid, key))
    else:
        await dbm.execute("UPDATE assets SET qty=qty-1 WHERE user_id=? AND kind='realty' AND item=?", (uid, key))
    await dbm.add_balance(uid, refund)
    return f"💸 Продано за {fmt(refund)} $"


@router.message(Command("business"))
@router.message(F.text == "🏢 Бизнесы")
async def h_biz(m: Message, user: dict):
    t, k = await render_section("biz", user["id"])
    await m.answer(t, reply_markup=k)


@router.message(Command("miners"))
@router.message(F.text == "🖥 Майнеры")
async def h_miners(m: Message, user: dict):
    t, k = await render_section("miner", user["id"])
    await m.answer(t, reply_markup=k)


@router.message(Command("realty"))
@router.message(F.text == "🏠 Недвижимость")
async def h_realty(m: Message, user: dict):
    t, k = await render_section("realty", user["id"])
    await m.answer(t, reply_markup=k)


@router.callback_query(F.data.startswith("sec:"))
async def cb_section(c: CallbackQuery, user: dict):
    parts = c.data.split(":")
    kind, action = parts[1], parts[2]
    key = parts[3] if len(parts) > 3 else None
    if kind not in DATA:
        return await c.answer()
    notice = None

    if action == "collect":
        amount = await game.collect_kind(user, kind)
        notice = f"💰 +{fmt_f(amount)} SKR" if kind == "miner" else f"💰 +{fmt(amount)} $"
    elif action == "buy":
        notice = await do_buy(user["id"], kind, key)
    elif action == "sell" and kind == "realty":
        notice = await do_sell_realty(user["id"], key)
    elif action == "sellskr" and kind == "miner":
        u = await dbm.get_user(user["id"])
        rate = await dbm.get_rate()
        money = int(u["skr"] * rate)
        if money <= 0:
            notice = "❌ Нет SKR для продажи"
        else:
            await dbm.execute("UPDATE users SET skr=0 WHERE id=?", (user["id"],))
            await dbm.add_balance(user["id"], money)
            notice = f"💱 Продано за {fmt(money)} $"

    text, kb = await render_section(kind, user["id"])
    await safe_edit(c, text, kb)
    await c.answer(notice or "", show_alert=bool(notice and notice.startswith("❌")))


# ======================= РАБОТА / БОНУС =======================
JOBS = [
    "разгрузил вагон", "починил чей-то сервер", "развёз пиццу", "написал пару скриптов",
    "отработал смену на складе", "сыграл на гитаре в переходе", "помыл витрины",
]


@router.message(Command("work"))
@router.message(F.text == "💼 Работа")
async def h_work(m: Message, user: dict):
    now = time.time()
    prem = is_premium(user)
    cd = PREMIUM_WORK_COOLDOWN if prem else WORK_COOLDOWN
    left = cd - (now - user["last_work"])
    if left > 0:
        return await m.answer(f"⏳ Следующая смена через {fmt_dur(left)}")
    assets = await dbm.get_assets(user["id"])
    rate = await dbm.get_rate()
    reward = random.randint(150, 400) + int(game.income_per_hour(user, assets, rate) * 0.25)
    if prem:
        reward = int(reward * PREMIUM_WORK_MULT)
    await dbm.execute(
        "UPDATE users SET balance=balance+?, last_work=? WHERE id=?", (reward, now, user["id"])
    )
    await m.answer(f"💼 Ты {random.choice(JOBS)} и заработал <b>{fmt(reward)} $</b>")


@router.message(Command("bonus"))
@router.message(F.text == "🎁 Бонус")
async def h_bonus(m: Message, user: dict):
    now = time.time()
    left = BONUS_COOLDOWN - (now - user["last_bonus"])
    if left > 0:
        return await m.answer(f"🎁 Следующий бонус через {fmt_dur(left)}")
    streak = user["streak"] + 1 if now - user["last_bonus"] < BONUS_COOLDOWN * 2 else 1
    reward = 500 * min(streak, 7)
    if is_premium(user):
        reward *= PREMIUM_BONUS_MULT
    await dbm.execute(
        "UPDATE users SET balance=balance+?, last_bonus=?, streak=? WHERE id=?",
        (reward, now, streak, user["id"]),
    )
    await m.answer(f"🎁 Ежедневный бонус: <b>+{fmt(reward)} $</b>\n🔥 Серия: {streak} дн. (макс. награда с 7-го дня)")


# ======================= КАЗИНО =======================
def casino_kb():
    return ikb([
        [btn("100", "casino:100"), btn("1 000", "casino:1000"), btn("10 000", "casino:10000")],
        [btn("100 000", "casino:100000"), btn("🎲 Ва-банк", "casino:all")],
    ])


async def play_casino(user, bet):
    u = await dbm.get_user(user["id"])
    if bet == "all":
        bet = min(u["balance"], CASINO_MAX_BET)
    if bet < CASINO_MIN_BET:
        return f"❌ Минимальная ставка — {CASINO_MIN_BET} $", False
    if bet > CASINO_MAX_BET:
        return f"❌ Максимальная ставка — {fmt(CASINO_MAX_BET)} $", False
    if bet > u["balance"]:
        return "❌ Недостаточно денег", False
    p_win = PREMIUM_CASINO_WIN_CHANCE if is_premium(u) else CASINO_WIN_CHANCE
    r = random.random()
    if r < CASINO_JACKPOT_CHANCE:
        net, label = bet * 4, "🎰 <b>ДЖЕКПОТ x5!</b>"
    elif r < CASINO_JACKPOT_CHANCE + p_win:
        net, label = bet, "✅ <b>Победа x2!</b>"
    else:
        net, label = -bet, "❌ <b>Проигрыш</b>"
    await dbm.add_balance(u["id"], net)
    nb = u["balance"] + net
    sign = "+" if net > 0 else "−"
    return f"{label}\n{sign}{fmt(abs(net))} $\n💰 Баланс: {fmt(nb)} $", True


@router.message(Command("casino"))
@router.message(F.text == "🎰 Казино")
async def h_casino(m: Message, user: dict, command: CommandObject = None):
    arg = (command.args or "").strip().lower() if command else ""
    if arg:
        if arg in ("all", "всё", "все"):
            bet = "all"
        elif arg.isdigit():
            bet = int(arg)
        else:
            return await m.answer("Использование: /casino [ставка]")
        text, _ = await play_casino(user, bet)
        return await m.answer(text, reply_markup=casino_kb())
    p = int((PREMIUM_CASINO_WIN_CHANCE if is_premium(user) else CASINO_WIN_CHANCE) * 100)
    await m.answer(
        f"🎰 <b>Казино</b>\n\nШанс победы (x2): {p}%\nДжекпот (x5): {int(CASINO_JACKPOT_CHANCE * 100)}%\n"
        f"Ставка: {CASINO_MIN_BET}–{fmt(CASINO_MAX_BET)} $\n\nВыбери ставку или напиши /casino сумма",
        reply_markup=casino_kb(),
    )


@router.callback_query(F.data.startswith("casino:"))
async def cb_casino(c: CallbackQuery, user: dict):
    arg = c.data.split(":")[1]
    bet = "all" if arg == "all" else int(arg)
    text, ok = await play_casino(user, bet)
    if not ok:
        return await c.answer(text, show_alert=True)
    await safe_edit(c, text, casino_kb())
    await c.answer()


# ======================= ПЕРЕВОДЫ / ПРОМОКОДЫ =======================
@router.message(Command("pay"))
async def h_pay(m: Message, command: CommandObject, user: dict, bot: Bot):
    args = (command.args or "").split()
    target, amount_s = None, None
    if m.reply_to_message and m.reply_to_message.from_user and len(args) == 1:
        target = await dbm.get_user(m.reply_to_message.from_user.id)
        amount_s = args[0]
    elif len(args) == 2:
        target = await dbm.find_user(args[0])
        amount_s = args[1]
    else:
        return await m.answer("Использование: /pay [@ник|ID] [сумма]\nили ответом на сообщение: /pay [сумма]")

    if target is None:
        return await m.answer("❌ Игрок не найден (он должен был запускать бота)")
    if target["id"] == user["id"]:
        return await m.answer("❌ Нельзя переводить самому себе")
    if not amount_s.isdigit():
        return await m.answer("❌ Сумма должна быть числом")
    amount = int(amount_s)
    if amount < MIN_TRANSFER:
        return await m.answer(f"❌ Минимальный перевод — {MIN_TRANSFER} $")

    fee_rate = PREMIUM_TRANSFER_FEE if is_premium(user) else TRANSFER_FEE
    fee = int(amount * fee_rate)
    if not await dbm.spend(user["id"], amount):
        return await m.answer("❌ Недостаточно денег")
    await dbm.add_balance(target["id"], amount - fee)
    await m.answer(f"✅ Переведено {fmt(amount - fee)} $ → {short_name(target)}\nКомиссия: {fmt(fee)} $ ({fee_rate * 100:g}%)")
    try:
        await bot.send_message(target["id"], f"💸 {short_name(user)} перевёл вам <b>{fmt(amount - fee)} $</b>")
    except Exception:
        pass


@router.message(Command("promo"))
async def h_promo(m: Message, command: CommandObject, user: dict):
    code = (command.args or "").strip().upper()
    if not code:
        return await m.answer("Использование: /promo [код]")
    p = await dbm.fetchone("SELECT * FROM promos WHERE code=?", (code,))
    if not p or p["uses"] <= 0:
        return await m.answer("❌ Промокод недействителен")
    if await dbm.fetchone("SELECT 1 AS x FROM promo_used WHERE user_id=? AND code=?", (user["id"], code)):
        return await m.answer("❌ Вы уже активировали этот промокод")
    n = await dbm.execute("UPDATE promos SET uses=uses-1 WHERE code=? AND uses>0", (code,))
    if n == 0:
        return await m.answer("❌ Промокод закончился")
    await dbm.execute("INSERT INTO promo_used(user_id, code) VALUES(?,?)", (user["id"], code))
    await dbm.add_balance(user["id"], p["amount"])
    await m.answer(f"🎟 Промокод активирован: <b>+{fmt(p['amount'])} $</b>")


# ======================= ПРОФИЛЬ =======================
@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def h_profile(m: Message, user: dict, bot: Bot):
    u = await dbm.get_user(user["id"])
    assets = await dbm.get_assets(u["id"])
    rate = await dbm.get_rate()
    dep = await dbm.fetchone("SELECT amount FROM deposits WHERE user_id=?", (u["id"],))
    dep_amount = dep["amount"] if dep else 0
    worth = u["balance"] + dep_amount + u["skr"] * rate
    inc = game.income_per_hour(u, assets, rate)
    if is_premium(u):
        until = datetime.fromtimestamp(u["premium_until"]).strftime("%d.%m.%Y %H:%M")
        prem = f"до {until}"
    else:
        prem = "нет"
    me = await bot_username(bot)
    await m.answer(
        f"👤 <b>{badges(u)} {short_name(u)}</b>\n"
        f"🆔 <code>{u['id']}</code>\n\n"
        f"💰 Баланс: <b>{fmt(u['balance'])} $</b>\n"
        f"🏦 Во вкладе: {fmt(dep_amount)} $\n"
        f"🪙 SKR: {fmt_f(u['skr'])} ≈ {fmt(u['skr'] * rate)} $\n"
        f"📈 Доход: {fmt(inc)} $/ч\n"
        f"🏦 Состояние: {fmt(worth)} $\n\n"
        f"🔨 Кирка: ур. {u['pickaxe']} · ударов: {fmt(u['mined'])}\n"
        f"💎 Премиум: {prem}\n"
        f"👥 Приглашено: {u['refs']} (+{fmt(REF_BONUS)} $ за каждого)\n"
        f"🔗 <code>https://t.me/{me}?start=ref_{u['id']}</code>"
    )


# ======================= ТОП =======================
async def render_top(by, uid):
    rows = await game.build_top()
    key = "worth" if by == "wealth" else "income"
    rows = sorted(rows, key=lambda r: r[key], reverse=True)
    unit = "$" if by == "wealth" else "$/ч"
    title = "💰 <b>Топ по состоянию</b>" if by == "wealth" else "📈 <b>Топ по доходу</b>"
    medals = ["🥇", "🥈", "🥉"]
    lines = [title, ""]
    for i, r in enumerate(rows[:10]):
        place = medals[i] if i < 3 else f"{i + 1}."
        b = badges(r)
        lines.append(f"{place} {b + ' ' if b else ''}{short_name(r)} — {fmt(r[key])} {unit}")
    pos = next((i + 1 for i, r in enumerate(rows) if r["id"] == uid), None)
    if pos:
        lines.append(f"\n📍 Ваше место: #{pos}")
    lines.append("\n👑 — владелец · 💎 — премиум")
    kb = ikb([[btn("💰 По состоянию", "top:wealth"), btn("📈 По доходу", "top:income")]])
    return "\n".join(lines), kb


@router.message(Command("top"))
@router.message(F.text == "🏆 Топ")
async def h_top(m: Message, user: dict):
    t, k = await render_top("wealth", user["id"])
    await m.answer(t, reply_markup=k)


@router.callback_query(F.data.startswith("top:"))
async def cb_top(c: CallbackQuery, user: dict):
    t, k = await render_top(c.data.split(":")[1], user["id"])
    await safe_edit(c, t, k)
    await c.answer()


# ======================= ПРЕМИУМ =======================
def premium_text(u):
    status = ""
    if is_premium(u):
        until = datetime.fromtimestamp(u["premium_until"]).strftime("%d.%m.%Y %H:%M")
        status = f"✅ <b>Активен до {until}</b>\n\n"
    return (
        f"💎 <b>Премиум</b> · {PREMIUM_DAYS} дней\n\n{status}"
        "Что даёт:\n"
        "• 💎 значок слева от ника в топе\n"
        f"• +{int((PREMIUM_INCOME_MULT - 1) * 100)}% ко всему пассивному доходу\n"
        f"• +{int((PREMIUM_MINE_MULT - 1) * 100)}% в шахте и {int((PREMIUM_WORK_MULT - 1) * 100)}% на работе\n"
        f"• хранилище {PREMIUM_STORAGE_HOURS} ч вместо {STORAGE_HOURS} ч\n"
        f"• ежедневный бонус x{PREMIUM_BONUS_MULT}\n"
        f"• комиссия переводов {PREMIUM_TRANSFER_FEE * 100:g}% вместо {TRANSFER_FEE * 100:g}%\n"
        f"• смена на работе каждые {PREMIUM_WORK_COOLDOWN // 60} мин\n"
        f"• шанс победы в казино {int(PREMIUM_CASINO_WIN_CHANCE * 100)}%\n\n"
        f"💳 Цена: <b>{PREMIUM_PRICE_RUB} ₽</b> или <b>{PREMIUM_PRICE_STARS} ⭐</b>\n\n"
        f"Как купить: отправь подарок на {PREMIUM_PRICE_STARS} ⭐ или переведи {PREMIUM_PRICE_RUB} ₽ "
        f"пользователю {PREMIUM_CONTACT}, затем нажми «Я оплатил(а)». "
        f"Админ проверит и выдаст премиум.\n\n"
        f"Твой ID: <code>{u['id']}</code>"
    )


def premium_kb():
    return ikb([
        [btn(f"💬 Написать {PREMIUM_CONTACT}", url=f"https://t.me/{PREMIUM_CONTACT.lstrip('@')}")],
        [btn("✅ Я оплатил(а)", "prem:paid")],
    ])


@router.message(Command("premium"))
@router.message(F.text == "💎 Премиум")
async def h_premium(m: Message, user: dict):
    await m.answer(premium_text(user), reply_markup=premium_kb())


@router.callback_query(F.data == "prem:paid")
async def cb_prem_paid(c: CallbackQuery, user: dict, bot: Bot):
    pend = await dbm.fetchone(
        "SELECT id FROM premium_requests WHERE user_id=? AND status='pending'", (user["id"],)
    )
    if pend:
        return await c.answer("Заявка уже отправлена, ожидайте подтверждения ⏳", show_alert=True)
    await dbm.execute(
        "INSERT INTO premium_requests(user_id, created) VALUES(?,?)", (user["id"], time.time())
    )
    req = await dbm.fetchone(
        "SELECT id FROM premium_requests WHERE user_id=? AND status='pending'", (user["id"],)
    )
    uname = f"@{user['username']}" if user["username"] else "без username"
    text = (
        f"💎 <b>Заявка на премиум #{req['id']}</b>\n"
        f"Игрок: {short_name(user)} ({uname})\nID: <code>{user['id']}</code>\n\n"
        f"Проверьте поступление подарка ({PREMIUM_PRICE_STARS} ⭐) или перевода ({PREMIUM_PRICE_RUB} ₽)."
    )
    kb = ikb([[btn("✅ Выдать", f"pa:ok:{req['id']}"), btn("❌ Отклонить", f"pa:no:{req['id']}")]])
    for admin_id in ADMIN_SET:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb)
        except Exception:
            pass
    await c.answer("✅ Заявка отправлена администраторам", show_alert=True)
