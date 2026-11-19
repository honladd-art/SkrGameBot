"""Текстовые команды без «/» для личных сообщений."""
import re
from types import SimpleNamespace

from aiogram import F, Router

from matching import norm
import user_handlers as uh
import extra_handlers as ex
import textcmds as tc

router = Router()


def _none(a):
    return a is None


def _any(a):
    return a is not None


def _num(a):
    return a is None or re.fullmatch(r"\d+|все|всё|all", a.lower()) is not None


def _pay(a):
    return a is not None and re.search(r"\d", a) is not None


def _one(a):
    return a is not None and len(a.split()) == 1


def _top(a):
    return a is None or norm(a) in {"доход", "доходу", "состояние", "богатство", "деньги"}


COLLECT_ARGS = {"бизнес", "бизнесы", "майнеры", "майнер", "ферма", "недвижимость", "огород",
                "урожай", "грядки", "вклад", "депозит", "банк", "все", "всё"}


def _collect(a):
    return a is None or norm(a) in COLLECT_ARGS


# команда -> (слова, проверка аргументов)
WORDS = {
    "mine": (["шахта", "копать", "копай", "майнить"], _none),
    "work": (["работа", "работать", "подработка"], _none),
    "business": (["бизнес", "бизнесы"], _none),
    "miners": (["майнеры", "майнер", "ферма"], _none),
    "realty": (["недвижимость", "дом", "дома"], _none),
    "bonus": (["бонус", "ежедневка"], _none),
    "casino": (["казино", "казик"], _num),
    "pay": (["перевод", "передать"], _pay),
    "promo": (["промо", "промокод"], _one),
    "top": (["топ", "рейтинг"], _top),
    "profile": (["профиль", "баланс", "я"], _none),
    "premium": (["премиум", "прем"], _none),
    "help": (["помощь", "команды", "хелп"], _none),
    "start": (["старт", "начать"], _none),
    "fish": (["рыбалка", "рыбачить", "ловить", "рыба"], _none),
    "garden": (["огород", "грядки"], _none),
    "bank": (["банк", "вклад"], _num),
    "deposit": (["депозит"], _num),
    "pickaxe": (["кирка", "кирку"], _none),
    "upgrade": (["улучшить", "улучшение", "апгрейд"], _any),
    "buy": (["купить", "купи"], _any),
    "sell": (["продать", "продай"], _any),
    "collect": (["собрать", "сбор", "забрать"], _collect),
    "harvest": (["урожай", "жатва"], _none),
    "plant": (["посадить", "посади", "сажать"], _any),
    "bank_take": (["снять"], _none),
    "early": (["досрочно"], _none),
    "paid": (["оплатил", "оплатила"], _none),
}

PRIVATE_ONLY_WORDS = {"я", "дом", "дома", "рыба", "ловить", "ферма", "старт", "начать",
                      "помощь", "команды", "хелп", "банк", "сбор"}

INDEX = {}
for _cmd, (_words, _check) in WORDS.items():
    for _word in _words:
        INDEX.setdefault(_word, (_cmd, _check))


def parse(text, group=False):
    """Возвращает (команда, аргументы) или None."""
    if not text or text.startswith("/"):
        return None
    parts = text.strip().split(maxsplit=1)
    if not parts:
        return None
    word = parts[0].lower().strip("!?.,:;")
    hit = INDEX.get(word)
    if not hit:
        return None
    cmd, check = hit
    args = parts[1].strip() if len(parts) > 1 else None
    if group and (word in PRIVATE_ONLY_WORDS or not check(args)):
        return None
    return cmd, args


HANDLERS = {
    "mine": uh.h_mine,
    "work": uh.h_work,
    "business": uh.h_biz,
    "miners": uh.h_miners,
    "realty": uh.h_realty,
    "bonus": uh.h_bonus,
    "casino": uh.h_casino,
    "pay": uh.h_pay,
    "promo": uh.h_promo,
    "top": uh.h_top,
    "profile": uh.h_profile,
    "premium": uh.h_premium,
    "help": uh.h_help,
    "start": uh.h_start,
    "fish": ex.h_fish,
    "garden": ex.h_garden,
    "bank": ex.h_bank,
    "deposit": ex.h_deposit,
    "pickaxe": tc.h_pickaxe,
    "upgrade": tc.h_upgrade,
    "buy": tc.h_buy,
    "sell": tc.h_sell,
    "collect": tc.h_collect,
    "harvest": tc.h_harvest,
    "plant": tc.h_plant,
    "bank_take": tc.h_bank_take,
    "early": tc.h_early,
    "paid": tc.h_paid,
}

COMMAND_ARG_HANDLERS = {"casino", "pay", "promo", "bank", "deposit", "upgrade", "buy", "sell",
                        "collect", "plant"}


@router.message(F.text)
async def handle_text_alias(message, user, bot):
    parsed = parse(message.text)
    if parsed is None:
        return
    command_name, args = parsed
    handler = HANDLERS.get(command_name)
    if handler is None:
        return
    if command_name in COMMAND_ARG_HANDLERS:
        command = SimpleNamespace(args=args)
        await handler(message, user=user, command=command, **({"bot": bot} if command_name == "pay" else {}))
    elif command_name in {"profile", "paid"}:
        await handler(message, user=user, bot=bot)
    else:
        await handler(message, user=user)
