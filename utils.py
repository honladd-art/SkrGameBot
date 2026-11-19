import html
import time

from config import OWNER_IDS, ADMIN_SET


def fmt(n):
    return f"{int(n):,}".replace(",", " ")


def fmt_f(x, d=2):
    return f"{x:,.{d}f}".replace(",", " ")


def esc(s):
    return html.escape(str(s or ""))


def short_name(u):
    name = (u.get("name") or "Игрок").strip() or "Игрок"
    return esc(name[:20])


def is_premium(u):
    return float(u.get("premium_until") or 0) > time.time()


def is_owner(uid):
    return uid in OWNER_IDS


def is_admin(uid):
    return uid in ADMIN_SET


def badges(u):
    """Значки слева от ника: 👑 владелец, 💎 премиум."""
    b = ""
    if is_owner(u["id"]):
        b += "👑"
    if is_premium(u):
        b += "💎"
    return b


def fmt_dur(sec):
    sec = int(max(sec, 0))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h} ч {m} мин"
    if m:
        return f"{m} мин {s} сек"
    return f"{s} сек"
