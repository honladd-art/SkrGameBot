import random
import time

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery

import database as dbm
import game
from game_data import *
from utils import fmt, is_premium, fmt_dur
from user_handlers import btn, ikb, safe_edit

router = Router()


# ---------- кулдауны ----------
async def get_cd(uid, key):
    r = await dbm.fetchone("SELECT ts FROM cd WHERE user_id=? AND key=?", (uid, key))
    return r["ts"] if r else 0


async def set_cd(uid, key, ts):
    await dbm.execute(
        "INSERT INTO cd(user_id, key, ts) VALUES(?,?,?) ON CONFLICT(user_id, key) DO UPDATE SET ts=excluded.ts",
        (uid, key, ts),
    )


# ======================= РЫБАЛКА =======================
def fish_kb():
    return ikb([[btn("🎣 Забросить удочку", "fish:cast")]])


async def do_fish(user):
    now = time.time()
    cd = PREMIUM_FISH_COOLDOWN if is_premium(user) else FISH_COOLDOWN
    left = cd - (now - await get_cd(user["id"], "fish"))
    if left > 0:
        return False, f"⏳ Рыба клюнет через {fmt_dur(left)}"
    weights = [x[0] for x in FISH_LOOT]
    _, name, (lo, hi) = random.choices(FISH_LOOT, weights=weights, k=1)[0]
    reward = random.randint(lo, hi)
    assets = await dbm.get_assets(user["id"])
    rate = await dbm.get_rate()
    reward += int(game.income_per_hour(user, assets, rate) * 0.05)
    if is_premium(user):
        reward = int(reward * PREMIUM_WORK_MULT)
    await dbm.add_balance(user["id"], reward)
    await set_cd(user["id"], "fish", now)
    return True, f"🎣 Улов: {name}\n💰 Продано за <b>{fmt(reward)} $</b>"


@router.message(Command("fish"))
@router.message(F.text == "🎣 Рыбалка")
async def h_fish(m: Message, user: dict):
    ok, text = await do_fish(user)
    await m.answer(text, reply_markup=fish_kb())


@router.callback_query(F.data == "fish:cast")
async def cb_fish(c: CallbackQuery, user: dict):
    ok, text = await do_fish(user)
    if not ok:
        return await c.answer(text)
    await safe_edit(c, text, fish_kb())
    await c.answer()


# ======================= ОГОРОД =======================
def plots_for(u):
    return PREMIUM_GARDEN_PLOTS if is_premium(u) else GARDEN_PLOTS


async def render_garden(uid):
    u = await dbm.get_user(uid)
    rows = await dbm.fetchall("SELECT * FROM farm WHERE user_id=?", (uid,))
    by = {r["slot"]: r for r in rows}
    now = time.time()
    plots = plots_for(u)
    lines = ["🌱 <b>Огород</b>\n"]
    ready_sum, ready_cnt = 0, 0
    mult = PREMIUM_INCOME_MULT if is_premium(u) else 1.0
    for slot in range(1, max(plots, max(by, default=0)) + 1):
        r = by.get(slot)
        if not r:
            lines.append(f"⬜ Грядка {slot}: пусто")
            continue
        c = CROPS[r["crop"]]
        if r["ready_at"] <= now:
            lines.append(f"✅ Грядка {slot}: {c['emoji']} {c['name']} — готово!")
            ready_sum += int(c["yield"] * mult)
            ready_cnt += 1
        else:
            lines.append(f"🌱 Грядка {slot}: {c['emoji']} {c['name']} — ещё {fmt_dur(r['ready_at'] - now)}")
    lines.append(f"\n💰 Баланс: <b>{fmt(u['balance'])} $</b>")
    kb = []
    if ready_cnt:
        kb.append([btn(f"🌾 Собрать урожай +{fmt(ready_sum)} $", "garden:harvest")])
    free = [s for s in range(1, plots + 1) if s not in by]
    if free:
        lines.append(f"Свободно грядок: {len(free)}. Что посадить?")
        for key, c in CROPS.items():
            kb.append([btn(f"{c['emoji']} {c['name']} · {fmt(c['cost'])} $ → {fmt(c['yield'])} $ · {fmt_dur(c['seconds'])}", f"garden:plant:{key}")])
    return "\n".join(lines), ikb(kb)


@router.message(Command("garden"))
@router.message(F.text == "🌱 Огород")
async def h_garden(m: Message, user: dict):
    t, k = await render_garden(user["id"])
    await m.answer(t, reply_markup=k)


async def garden_plant(uid, crop_key):
    u = await dbm.get_user(uid)
    crop = CROPS[crop_key]
    rows = await dbm.fetchall("SELECT slot FROM farm WHERE user_id=?", (uid,))
    taken = {r["slot"] for r in rows}
    free = [s for s in range(1, plots_for(u) + 1) if s not in taken]
    if not free:
        return "❌ Нет свободных грядок"
    if not await dbm.spend(uid, crop["cost"]):
        return f"❌ Не хватает {fmt(crop['cost'] - u['balance'])} $"
    await dbm.execute(
        "INSERT INTO farm(user_id, slot, crop, ready_at) VALUES(?,?,?,?)",
        (uid, free[0], crop_key, time.time() + crop["seconds"]),
    )
    return f"{crop['emoji']} {crop['name']} посажено! Созреет через {fmt_dur(crop['seconds'])}"


async def garden_harvest(uid):
    u = await dbm.get_user(uid)
    now = time.time()
    rows = await dbm.fetchall("SELECT * FROM farm WHERE user_id=? AND ready_at<=?", (uid, now))
    if not rows:
        return "🌱 Пока ничего не созрело"
    mult = PREMIUM_INCOME_MULT if is_premium(u) else 1.0
    total = sum(int(CROPS[r["crop"]]["yield"] * mult) for r in rows)
    await dbm.execute("DELETE FROM farm WHERE user_id=? AND ready_at<=?", (uid, now))
    await dbm.add_balance(uid, total)
    return f"🌾 Собрано: +{fmt(total)} $"


@router.callback_query(F.data.startswith("garden:"))
async def cb_garden(c: CallbackQuery, user: dict):
    parts = c.data.split(":")
    uid = user["id"]
    notice = None
    if parts[1] == "plant" and len(parts) > 2 and parts[2] in CROPS:
        notice = await garden_plant(uid, parts[2])
    elif parts[1] == "harvest":
        notice = await garden_harvest(uid)
    text, kb = await render_garden(uid)
    await safe_edit(c, text, kb)
    await c.answer(notice or "", show_alert=bool(notice and notice.startswith("❌")))


# ======================= БАНК (ВКЛАД) =======================
async def render_bank(uid):
    u = await dbm.get_user(uid)
    dep = await dbm.fetchone("SELECT * FROM deposits WHERE user_id=?", (uid,))
    now = time.time()
    prem = is_premium(u)
    max_dep = PREMIUM_BANK_MAX if prem else BANK_MAX
    rate = PREMIUM_BANK_INTEREST if prem else BANK_INTEREST
    lines = ["🏦 <b>Банк</b>\n"]
    kb = []
    if dep:
        interest = int(dep["amount"] * dep["rate"])
        end = dep["started"] + BANK_TERM
        lines.append(f"Вклад: <b>{fmt(dep['amount'])} $</b> под {dep['rate'] * 100:g}% за {BANK_TERM // 3600} ч")
        if now >= end:
            lines.append(f"✅ Срок вышел! К выплате: <b>{fmt(dep['amount'] + interest)} $</b>")
            kb.append([btn(f"💰 Забрать +{fmt(dep['amount'] + interest)} $", "bank:take")])
        else:
            lines.append(f"⏳ До выплаты: {fmt_dur(end - now)} (+{fmt(interest)} $)")
            kb.append([btn("↩️ Забрать досрочно (без процентов)", "bank:early")])
    else:
        lines.append(
            f"Положи деньги на {BANK_TERM // 3600} ч и получи <b>{rate * 100:g}%</b> сверху.\n"
            f"Сумма: {fmt(BANK_MIN)} – {fmt(max_dep)} $ (одновременно один вклад).\n"
            "Свою сумму: /deposit сумма"
        )
        kb.append([btn("1 000", "bank:open:1000"), btn("10 000", "bank:open:10000"), btn("100 000", "bank:open:100000")])
        kb.append([btn("💼 Всё, что можно", "bank:open:all")])
    lines.append(f"\n💰 Баланс: <b>{fmt(u['balance'])} $</b>")
    return "\n".join(lines), ikb(kb)


async def open_deposit(uid, amount):
    u = await dbm.get_user(uid)
    if await dbm.fetchone("SELECT 1 AS x FROM deposits WHERE user_id=?", (uid,)):
        return "❌ У вас уже есть активный вклад"
    prem = is_premium(u)
    max_dep = PREMIUM_BANK_MAX if prem else BANK_MAX
    if amount == "all":
        amount = min(u["balance"], max_dep)
    if amount < BANK_MIN:
        return f"❌ Минимальный вклад — {fmt(BANK_MIN)} $"
    if amount > max_dep:
        return f"❌ Максимальный вклад — {fmt(max_dep)} $"
    if not await dbm.spend(uid, amount):
        return "❌ Недостаточно денег"
    rate = PREMIUM_BANK_INTEREST if prem else BANK_INTEREST
    await dbm.execute(
        "INSERT INTO deposits(user_id, amount, rate, started) VALUES(?,?,?,?)",
        (uid, amount, rate, time.time()),
    )
    return f"🏦 Вклад {fmt(amount)} $ открыт!"


@router.message(Command("bank"))
@router.message(F.text == "🏦 Банк")
async def h_bank(m: Message, user: dict, command: CommandObject = None):
    if command and (command.args or "").strip():
        return await h_deposit(m, command, user)  # «вклад 5000»
    t, k = await render_bank(user["id"])
    await m.answer(t, reply_markup=k)


@router.message(Command("deposit"))
async def h_deposit(m: Message, command: CommandObject, user: dict):
    arg = (command.args or "").strip().lower()
    if arg in ("all", "всё", "все"):
        amount = "all"
    elif arg.isdigit():
        amount = int(arg)
    else:
        return await m.answer("Использование: /deposit [сумма]")
    notice = await open_deposit(user["id"], amount)
    t, k = await render_bank(user["id"])
    await m.answer(f"{notice}\n\n{t}", reply_markup=k)


async def bank_take(uid, early=False):
    dep = await dbm.fetchone("SELECT * FROM deposits WHERE user_id=?", (uid,))
    if not dep:
        return "❌ У вас нет вклада"
    now = time.time()
    end = dep["started"] + BANK_TERM
    ready = now >= end
    if not early and not ready:
        return f"⏳ Срок ещё не вышел: {fmt_dur(end - now)}. Досрочно (без процентов) — «досрочно»"
    payout = dep["amount"] + (int(dep["amount"] * dep["rate"]) if ready else 0)
    n = await dbm.execute("DELETE FROM deposits WHERE user_id=?", (uid,))
    if not n:
        return "❌ Вклад не найден"
    await dbm.add_balance(uid, payout)
    return f"💰 Получено {fmt(payout)} $"


@router.callback_query(F.data.startswith("bank:"))
async def cb_bank(c: CallbackQuery, user: dict):
    parts = c.data.split(":")
    action = parts[1]
    uid = user["id"]
    notice = None
    if action == "open":
        arg = parts[2]
        notice = await open_deposit(uid, "all" if arg == "all" else int(arg))
    elif action in ("take", "early"):
        notice = await bank_take(uid, early=(action == "early"))
    text, kb = await render_bank(uid)
    await safe_edit(c, text, kb)
    await c.answer(notice or "", show_alert=bool(notice and notice.startswith("❌")))
