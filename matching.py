"""Поиск объектов игры по свободному названию («кофейня», «квартиру», «картошка»)."""
import re

from game_data import DATA, CROPS

# особые прозвища
ALT = {
    "асик": ("miner", "asic"), "asic": ("miner", "asic"), "асиц": ("miner", "asic"),
    "пк": ("miner", "old_pc"), "комп": ("miner", "old_pc"), "компьютер": ("miner", "old_pc"),
    "видюха": ("miner", "gpu_rig"), "шаурма": ("biz", "shawarma"), "кафе": ("biz", "coffee"),
    "цод": ("miner", "datacenter"),
}


def norm(s):
    return (s or "").lower().replace("ё", "е").strip()


def _match(a, w):
    """Слова совпадают по началу (учитывает падежи: кофейня/кофейню)."""
    n = min(5, max(3, min(len(a), len(w)) - 1))
    return len(a) >= 3 and len(w) >= 3 and a[:n] == w[:n]


def _words(name):
    return [w for w in re.split(r"[\s\-]+", norm(name)) if w]


def find_items(arg):
    """Возвращает список (kind, key) подходящих бизнесов / майнеров / недвижимости."""
    a = norm(arg)
    if not a:
        return []
    if a in ALT:
        return [ALT[a]]
    exact, part = [], []
    for kind, data in DATA.items():
        for key, it in data.items():
            name = norm(it["name"])
            if a == name or a == key:
                exact.append((kind, key))
            elif len(a) >= 3 and (a in name or any(_match(a, w) for w in _words(it["name"]))):
                part.append((kind, key))
    return exact or part


def find_crop(arg):
    a = norm(arg)
    if not a:
        return None
    for key, c in CROPS.items():
        name = norm(c["name"])
        if a == name or a == key or a in name or any(_match(a, w) for w in _words(c["name"])):
            return key
    return None
