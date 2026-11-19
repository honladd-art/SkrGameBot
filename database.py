import time

import aiosqlite

from game_data import SKR_RATE_START, REF_BONUS

DB_PATH = "skrgame.db"
db: aiosqlite.Connection = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    balance INTEGER NOT NULL DEFAULT 0,
    skr REAL NOT NULL DEFAULT 0,
    pickaxe INTEGER NOT NULL DEFAULT 1,
    mined INTEGER NOT NULL DEFAULT 0,
    last_mine REAL NOT NULL DEFAULT 0,
    last_work REAL NOT NULL DEFAULT 0,
    last_bonus REAL NOT NULL DEFAULT 0,
    streak INTEGER NOT NULL DEFAULT 0,
    premium_until REAL NOT NULL DEFAULT 0,
    banned INTEGER NOT NULL DEFAULT 0,
    ref_by INTEGER,
    refs INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS assets(
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    item TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    qty INTEGER NOT NULL DEFAULT 1,
    last_collect REAL NOT NULL,
    PRIMARY KEY(user_id, kind, item)
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS promos(code TEXT PRIMARY KEY, amount INTEGER NOT NULL, uses INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS promo_used(user_id INTEGER NOT NULL, code TEXT NOT NULL, PRIMARY KEY(user_id, code));
CREATE TABLE IF NOT EXISTS premium_requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    created REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS cd(user_id INTEGER NOT NULL, key TEXT NOT NULL, ts REAL NOT NULL, PRIMARY KEY(user_id, key));
CREATE TABLE IF NOT EXISTS farm(
    user_id INTEGER NOT NULL, slot INTEGER NOT NULL, crop TEXT NOT NULL, ready_at REAL NOT NULL,
    PRIMARY KEY(user_id, slot)
);
CREATE TABLE IF NOT EXISTS deposits(
    user_id INTEGER PRIMARY KEY, amount INTEGER NOT NULL, rate REAL NOT NULL, started REAL NOT NULL
);
"""


async def init():
    global db
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.executescript(SCHEMA)
    await db.commit()


async def close():
    if db:
        await db.close()


# ---------- базовые ----------
async def fetchone(sql, args=()):
    async with db.execute(sql, args) as cur:
        r = await cur.fetchone()
    return dict(r) if r else None


async def fetchall(sql, args=()):
    async with db.execute(sql, args) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def execute(sql, args=()):
    cur = await db.execute(sql, args)
    await db.commit()
    n = cur.rowcount
    await cur.close()
    return n


# ---------- пользователи ----------
async def get_user(uid):
    return await fetchone("SELECT * FROM users WHERE id=?", (uid,))


async def find_user(arg):
    """Ищет игрока по ID или @username."""
    arg = arg.strip().lstrip("@")
    if arg.isdigit():
        return await get_user(int(arg))
    return await fetchone("SELECT * FROM users WHERE LOWER(username)=?", (arg.lower(),))


async def upsert_user(tg, ref=None):
    u = await get_user(tg.id)
    name = tg.full_name or "Игрок"
    uname = tg.username
    if u is None:
        ref_by = None
        if ref and ref != tg.id and await get_user(ref):
            ref_by = ref
        await execute(
            "INSERT INTO users(id, username, name, created, ref_by, balance) VALUES(?,?,?,?,?,?)",
            (tg.id, uname, name, time.time(), ref_by, REF_BONUS if ref_by else 0),
        )
        if ref_by:
            await execute("UPDATE users SET balance=balance+?, refs=refs+1 WHERE id=?", (REF_BONUS, ref_by))
        return await get_user(tg.id)
    if u["username"] != uname or u["name"] != name:
        await execute("UPDATE users SET username=?, name=? WHERE id=?", (uname, name, tg.id))
        u = await get_user(tg.id)
    return u


async def add_balance(uid, amount):
    await execute("UPDATE users SET balance=balance+? WHERE id=?", (int(amount), uid))


async def spend(uid, amount):
    """Атомарно списывает деньги. True, если хватило."""
    n = await execute(
        "UPDATE users SET balance=balance-? WHERE id=? AND balance>=?", (int(amount), uid, int(amount))
    )
    return n > 0


async def give_premium(uid, days):
    u = await get_user(uid)
    base = max(time.time(), float(u["premium_until"] or 0))
    new = base + days * 86400
    await execute("UPDATE users SET premium_until=? WHERE id=?", (new, uid))
    return new


# ---------- активы ----------
async def get_assets(uid, kind=None):
    if kind:
        return await fetchall("SELECT * FROM assets WHERE user_id=? AND kind=?", (uid, kind))
    return await fetchall("SELECT * FROM assets WHERE user_id=?", (uid,))


async def get_asset(uid, kind, item):
    return await fetchone(
        "SELECT * FROM assets WHERE user_id=? AND kind=? AND item=?", (uid, kind, item)
    )


async def add_asset(uid, kind, item, now):
    await execute(
        "INSERT INTO assets(user_id, kind, item, level, qty, last_collect) VALUES(?,?,?,1,1,?)",
        (uid, kind, item, now),
    )


# ---------- настройки / курс ----------
async def get_setting(key, default=None):
    r = await fetchone("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default


async def set_setting(key, value):
    await execute(
        "INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


async def get_rate():
    v = await get_setting("skr_rate")
    return float(v) if v else SKR_RATE_START


async def get_prev_rate():
    v = await get_setting("skr_rate_prev")
    return float(v) if v else await get_rate()
