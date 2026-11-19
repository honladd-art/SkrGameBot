import time

import database as dbm
from game_data import *
from utils import is_premium

_top_cache = {"t": 0, "data": None}


def mult(u):
    return PREMIUM_INCOME_MULT if is_premium(u) else 1.0


def storage_seconds(u):
    return (PREMIUM_STORAGE_HOURS if is_premium(u) else STORAGE_HOURS) * 3600


def rate_per_hour(kind, a):
    """Базовая отдача актива в час ($ или SKR)."""
    k = a["item"]
    if kind == "biz":
        return biz_income(k, a["level"])
    if kind == "miner":
        return MINERS[k]["yield"] * a["qty"]
    return REALTY[k]["rent"] * a["qty"]


def pending_amount(u, kind, a, now=None):
    now = now or time.time()
    elapsed = max(0, min(now - a["last_collect"], storage_seconds(u)))
    return rate_per_hour(kind, a) * elapsed / 3600 * mult(u)


async def collect_kind(u, kind):
    """Собирает накопленное по всем активам типа. Возвращает сумму ($ или SKR)."""
    now = time.time()
    assets = await dbm.get_assets(u["id"], kind)
    if not assets:
        return 0
    total = sum(pending_amount(u, kind, a, now) for a in assets)
    await dbm.execute(
        "UPDATE assets SET last_collect=? WHERE user_id=? AND kind=?", (now, u["id"], kind)
    )
    if kind == "miner":
        total = round(total, 4)
        await dbm.execute("UPDATE users SET skr=skr+? WHERE id=?", (total, u["id"]))
    else:
        total = int(total)
        await dbm.add_balance(u["id"], total)
    return total


def asset_value(kind, a):
    """Сколько денег вложено в актив (для рейтинга)."""
    k = a["item"]
    if kind == "biz":
        return BUSINESSES[k]["cost"] + sum(biz_upgrade_cost(k, l) for l in range(1, a["level"]))
    base = (MINERS if kind == "miner" else REALTY)[k]["cost"]
    return sum(unit_cost(base, i) for i in range(a["qty"]))


def income_per_hour(u, assets, skr_rate):
    """Суммарный доход в $/час (SKR пересчитан по курсу)."""
    total = 0.0
    for a in assets:
        r = rate_per_hour(a["kind"], a)
        total += r * skr_rate if a["kind"] == "miner" else r
    return total * mult(u)


async def build_top(force=False):
    now = time.time()
    if not force and _top_cache["data"] is not None and now - _top_cache["t"] < 60:
        return _top_cache["data"]
    users = await dbm.fetchall(
        "SELECT id, name, balance, skr, premium_until FROM users WHERE banned=0"
    )
    assets = await dbm.fetchall("SELECT * FROM assets")
    by = {}
    for a in assets:
        by.setdefault(a["user_id"], []).append(a)
    deps = {r["user_id"]: r["amount"] for r in await dbm.fetchall("SELECT user_id, amount FROM deposits")}
    rate = await dbm.get_rate()
    rows = []
    for u in users:
        al = by.get(u["id"], [])
        worth = u["balance"] + deps.get(u["id"], 0) + u["skr"] * rate
        rows.append(
            {
                "id": u["id"],
                "name": u["name"],
                "premium_until": u["premium_until"],
                "worth": int(worth),
                "income": int(income_per_hour(u, al, rate)),
            }
        )
    _top_cache["t"] = now
    _top_cache["data"] = rows
    return rows
