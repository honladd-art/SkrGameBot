# ============================================
#  ЭКОНОМИКА И ДАННЫЕ ИГРЫ
# ============================================

# --- Кулдауны (секунды) ---
MINE_COOLDOWN = 10
WORK_COOLDOWN = 3600
PREMIUM_WORK_COOLDOWN = 2400
BONUS_COOLDOWN = 86400

# --- Хранилище дохода (сколько часов копится без сбора) ---
STORAGE_HOURS = 12
PREMIUM_STORAGE_HOURS = 24

# --- Лимиты ---
MAX_BIZ_LEVEL = 15
MAX_QTY = 5            # максимум штук майнера / объекта недвижимости
MAX_PICKAXE = 20

# --- Бонусы премиума ---
PREMIUM_INCOME_MULT = 1.25
PREMIUM_MINE_MULT = 1.5
PREMIUM_WORK_MULT = 1.5
PREMIUM_BONUS_MULT = 2

# --- Прочее ---
REF_BONUS = 1000
REALTY_SELL_RATIO = 0.8
TRANSFER_FEE = 0.05
PREMIUM_TRANSFER_FEE = 0.02
MIN_TRANSFER = 100
CASINO_MIN_BET = 10
CASINO_MAX_BET = 5_000_000
CASINO_WIN_CHANCE = 0.45
PREMIUM_CASINO_WIN_CHANCE = 0.47
CASINO_JACKPOT_CHANCE = 0.01

# --- Курс SKR (криптовалюта майнеров), $ за 1 SKR ---
SKR_RATE_START = 40.0
SKR_RATE_MIN = 15.0
SKR_RATE_MAX = 90.0
SKR_RATE_TARGET = 40.0
SKR_UPDATE_SECONDS = 900

# --- Бизнесы: cost — цена, income — доход $/час на 1 уровне ---
BUSINESSES = {
    "shawarma":   {"name": "Ларёк с шаурмой", "emoji": "🌯", "cost": 500,         "income": 30},
    "coffee":     {"name": "Кофейня",         "emoji": "☕", "cost": 4_000,       "income": 220},
    "barber":     {"name": "Барбершоп",       "emoji": "💈", "cost": 15_000,      "income": 800},
    "shop":       {"name": "Магазин",         "emoji": "🛒", "cost": 60_000,      "income": 3_000},
    "restaurant": {"name": "Ресторан",        "emoji": "🍽", "cost": 250_000,     "income": 12_000},
    "hotel":      {"name": "Отель",           "emoji": "🏨", "cost": 1_000_000,   "income": 45_000},
    "factory":    {"name": "Завод",           "emoji": "🏭", "cost": 5_000_000,   "income": 210_000},
    "bank":       {"name": "Банк",            "emoji": "🏦", "cost": 25_000_000,  "income": 1_000_000},
}

# --- Майнеры: yield — SKR/час за 1 штуку ---
MINERS = {
    "old_pc":     {"name": "Старый ПК",     "emoji": "🖥", "cost": 2_000,      "yield": 2},
    "gpu_rig":    {"name": "Видеокарта",    "emoji": "🎮", "cost": 20_000,     "yield": 22},
    "asic":       {"name": "ASIC-майнер",   "emoji": "⚙️", "cost": 150_000,    "yield": 170},
    "farm":       {"name": "Майнинг-ферма", "emoji": "🏗", "cost": 1_000_000,  "yield": 1_200},
    "datacenter": {"name": "Дата-центр",    "emoji": "🏢", "cost": 8_000_000,  "yield": 10_000},
}

# --- Недвижимость: rent — аренда $/час за 1 штуку ---
REALTY = {
    "room":       {"name": "Комната",     "emoji": "🚪", "cost": 10_000,      "rent": 200},
    "flat":       {"name": "Квартира",    "emoji": "🏠", "cost": 80_000,      "rent": 1_500},
    "house":      {"name": "Дом",         "emoji": "🏡", "cost": 400_000,     "rent": 7_500},
    "villa":      {"name": "Вилла",       "emoji": "🏖", "cost": 2_000_000,   "rent": 40_000},
    "skyscraper": {"name": "Небоскрёб",   "emoji": "🌆", "cost": 15_000_000,  "rent": 320_000},
    "island":     {"name": "Свой остров", "emoji": "🏝", "cost": 100_000_000, "rent": 2_200_000},
}

DATA = {"biz": BUSINESSES, "miner": MINERS, "realty": REALTY}


# --- Формулы ---
def biz_income(key, level):
    return BUSINESSES[key]["income"] * level


def biz_upgrade_cost(key, level):
    """Цена улучшения с уровня level до level+1."""
    return int(BUSINESSES[key]["cost"] * 0.5 * level * 1.25 ** (level - 1))


def unit_cost(base, qty):
    """Цена следующей штуки, если уже куплено qty."""
    return int(base * (1 + 0.25 * qty))


def pickaxe_cost(level):
    return int(100 * 1.8 ** (level - 1))


def mine_range(level):
    mult = 1 + 0.5 * (level - 1)
    return int(8 * mult), int(15 * mult)


# --- Рыбалка ---
FISH_COOLDOWN = 300
PREMIUM_FISH_COOLDOWN = 200
# (шанс, название, (мин, макс) награда)
FISH_LOOT = [
    (0.30, "👢 Старый ботинок", (5, 30)),
    (0.45, "🐟 Карась", (40, 120)),
    (0.20, "🐠 Щука", (150, 400)),
    (0.05, "🐡 Золотая рыбка", (1000, 2500)),
]

# --- Огород ---
GARDEN_PLOTS = 3
PREMIUM_GARDEN_PLOTS = 5
CROPS = {
    "carrot":  {"name": "Морковь", "emoji": "🥕", "cost": 50,    "yield": 90,     "seconds": 300},
    "potato":  {"name": "Картофель", "emoji": "🥔", "cost": 200,   "yield": 380,    "seconds": 900},
    "pumpkin": {"name": "Тыква",   "emoji": "🎃", "cost": 1_000, "yield": 2_100,  "seconds": 3600},
    "melon":   {"name": "Арбуз",   "emoji": "🍉", "cost": 5_000, "yield": 11_500, "seconds": 14400},
}

# --- Банковский вклад ---
BANK_TERM = 4 * 3600          # срок вклада, секунд
BANK_INTEREST = 0.03          # процент за срок
PREMIUM_BANK_INTEREST = 0.05
BANK_MIN = 100
BANK_MAX = 1_000_000
PREMIUM_BANK_MAX = 2_000_000
