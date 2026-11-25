"""Telegram handlers (aiogram 3)."""
from __future__ import annotations

import asyncio
import logging
import random
from collections import defaultdict
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from ..game import new_world, start_career
from ..game.models import FORMATIONS, STYLES, TRAINING, World
from ..game.season import end_season, play_round, season_over
from ..game import transfers as tr
from ..storage import Storage
from . import views as v

log = logging.getLogger(__name__)
router = Router()
storage: Storage | None = None
_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
# careers that are being created (world generated, club not picked yet)
_pending: dict[int, World] = {}

LIVE_STEPS = (15, 30, 45, 60, 75, 90)
LIVE_DELAY = 1.6


def setup(st: Storage) -> Router:
    global storage
    storage = st
    return router


async def show(target, text: str, markup=None) -> None:
    """Edit the callback message in place, or send a new message."""
    if getattr(target, "data", None) is not None and hasattr(target, "message"):
        try:
            await target.message.edit_text(text, reply_markup=markup)
            return
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                return
        await target.message.answer(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


def manager_name(user) -> str:
    return (user.first_name or user.username or "Тренер")[:32]


# ------------------------------------------------------------------ commands
WELCOME = (
    "⚽ <b>Футбольний менеджер</b>\n\n"
    "Ти головний тренер і менеджер клубу. Склад, тактика, трансфери, фінанси, академія — усе на тобі. "
    "Виконуй ціль правління, піднімайся з Першої ліги до Прем’єр-ліги і вигравай трофеї.\n\n"
    "Команди: /menu — головне меню, /help — довідка, /top — зала слави."
)

HELP = (
    "📖 <b>Як грати</b>\n\n"
    "1. Обери клуб. У кожного своя репутація, бюджет і склад.\n"
    "2. Налаштуй <b>тактику</b>: схему й стиль гри. Склад на матч обирається автоматично з найкращих "
    "доступних гравців з урахуванням форми; щоб дати гравцю відпочити, натисни 💤 у його картці.\n"
    "3. Грай <b>тури</b>. Між матчами гравці відновлюються і прогресують залежно від тренувань і віку.\n"
    "4. <b>Трансфери</b> працюють у вікна: перші 3 тури і середина сезону. Вільних агентів можна брати будь-коли. "
    "Виставляй гравців на продаж, щоб отримувати пропозиції.\n"
    "5. <b>Фінанси</b>: доходи від квитків і спонсорів, витрати на зарплати. Вклади гроші в стадіон, базу й академію.\n"
    "6. Наприкінці сезону: призові, підвищення та пониження (по 2 клуби), старіння, вихованці академії.\n"
    "7. Якщо довіра правління впаде до нуля, тебе звільнять. Тримай результат!"
)


@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    world = storage.load(msg.from_user.id)
    if world and not world.fired:
        text, markup = v.main_menu(world)
        await msg.answer(WELCOME)
        await msg.answer(text, reply_markup=markup)
        return
    await msg.answer(WELCOME)
    await begin_new(msg, msg.from_user)


@router.message(Command("menu"))
async def cmd_menu(msg: Message) -> None:
    world = storage.load(msg.from_user.id)
    if not world:
        await begin_new(msg, msg.from_user)
        return
    text, markup = v.main_menu(world)
    await msg.answer(text, reply_markup=markup)


@router.message(Command("help"))
async def cmd_help(msg: Message) -> None:
    await msg.answer(HELP)


@router.message(Command("top"))
async def cmd_top(msg: Message) -> None:
    await msg.answer(hall_text())


@router.message(Command("new"))
async def cmd_new(msg: Message) -> None:
    await msg.answer("Почати нову кар’єру? Поточна буде видалена.",
                     reply_markup=v.kb([[("✅ Так, нова кар’єра", "newyes")], [("❌ Ні", "m")]]))


def hall_text() -> str:
    rows = storage.top(10)
    if not rows:
        return "🏅 <b>Зала слави</b>\n\nПоки порожньо. Стань першим!"
    lines = ["🏅 <b>Зала слави</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, (mgr, club, seasons, titles, promos, score) in enumerate(rows):
        m = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{m} {escape(mgr)} ({escape(club)}) · {score} очк. · 🏆{titles} ⬆️{promos} · {seasons} сез.")
    return "\n".join(lines)


async def begin_new(target, user) -> None:
    _pending[user.id] = new_world(user.id, manager_name(user))
    text, markup = v.choose_division_view()
    await show(target, text, markup)


# ------------------------------------------------------------------ callbacks
@router.callback_query(F.data == "noop")
async def cb_noop(cq: CallbackQuery) -> None:
    await cq.answer()


@router.callback_query(F.data == "pickdiv")
async def cb_pickdiv(cq: CallbackQuery) -> None:
    if cq.from_user.id not in _pending:
        _pending[cq.from_user.id] = new_world(cq.from_user.id, manager_name(cq.from_user))
    text, markup = v.choose_division_view()
    await show(cq, text, markup)
    await cq.answer()


@router.callback_query(F.data.startswith("pick:"))
async def cb_pick(cq: CallbackQuery) -> None:
    world = _pending.get(cq.from_user.id)
    if world is None:
        world = _pending[cq.from_user.id] = new_world(cq.from_user.id, manager_name(cq.from_user))
    div = int(cq.data.split(":")[1])
    text, markup = v.choose_club_view(world, div)
    await show(cq, text, markup)
    await cq.answer()


@router.callback_query(F.data.startswith("cc:"))
async def cb_choose_club(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    world = _pending.pop(uid, None)
    if world is None:
        await cq.answer("Сесія вибору застаріла, почни знову: /new", show_alert=True)
        return
    cid = int(cq.data.split(":")[1])
    old = storage.load(uid)
    if old:  # keep career history/trophies of previous job in hall of fame only
        storage.update_hall(old)
    start_career(world, cid)
    world.add_news(f"🤝 {world.manager} очолив {world.club.name}!")
    storage.save(world)
    await cq.answer("Вітаємо з призначенням!")
    text, markup = v.main_menu(world)
    await show(cq, f"🤝 Ти новий головний тренер <b>{escape(world.club.name)}</b>!\n\n" + text, markup)


@router.callback_query(F.data == "newask")
async def cb_newask(cq: CallbackQuery) -> None:
    await show(cq, "Почати нову кар’єру? Поточна буде видалена (рекорд у залі слави залишиться).",
               v.kb([[("✅ Так", "newyes")], [("❌ Ні", "m")]]))
    await cq.answer()


@router.callback_query(F.data == "newyes")
async def cb_newyes(cq: CallbackQuery) -> None:
    await begin_new(cq, cq.from_user)
    await cq.answer()


@router.callback_query(F.data == "hall")
async def cb_hall(cq: CallbackQuery) -> None:
    await show(cq, hall_text(), v.kb([v.back("club")]))
    await cq.answer()


# Everything below needs a loaded career --------------------------------------
GAME_PREFIXES = ("m", "nx", "play", "sq", "pl", "pa", "xi", "tac", "tf", "ts", "trn", "tt", "tb", "tbm", "sc", "fx",
                 "tr", "mk", "mp", "buy", "of", "oa", "or", "fin", "tp", "up", "club", "news", "endseason")


@router.callback_query(F.data.func(lambda d: d.split(":")[0] in GAME_PREFIXES))
async def cb_game(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    lock = _locks[uid]
    if lock.locked():
        await cq.answer("Зачекай, обробляю попередню дію…")
        return
    async with lock:
        world = storage.load(uid)
        if world is None:
            await cq.answer()
            await begin_new(cq, cq.from_user)
            return
        if world.fired:
            await cq.answer()
            await show(cq, "🚪 Правління тебе звільнило. Але кожен великий тренер колись починав заново!",
                       v.kb([[("🔄 Нова кар’єра", "newyes")], [("🏅 Зала слави", "hall")]]))
            return
        try:
            changed = await dispatch(cq, world)
        except Exception:  # keep the bot alive on unexpected errors
            log.exception("handler error for %s", cq.data)
            await cq.answer("Сталася помилка, спробуй ще раз.", show_alert=True)
            return
        if changed:
            storage.save(world)


async def dispatch(cq: CallbackQuery, world: World) -> bool:
    parts = cq.data.split(":")
    cmd = parts[0]
    alert = None
    changed = False
    text = markup = None

    if cmd == "m":
        text, markup = v.main_menu(world)
    elif cmd == "nx":
        if season_over(world):
            text, markup = "🏁 Усі тури зіграно!", v.kb([[("🏁 Підсумки сезону", "endseason")]])
        else:
            text, markup = v.preview_view(world)
    elif cmd == "play":
        await cq.answer()
        await play_match(cq, world, live=parts[1] == "live")
        return True
    elif cmd == "endseason":
        if not season_over(world):
            text, markup = v.main_menu(world)
        else:
            summary = end_season(world, random.Random())
            changed = True
            text = v.season_summary_text(world, summary)
            if world.fired:
                text += "\n\n🚪 Правління вирішило звільнити тебе. Спробуй себе в іншому клубі!"
                markup = v.kb([[("🔄 Нова кар’єра", "newyes")]])
            else:
                markup = v.kb([[("🚀 Новий сезон", "m")]])
    elif cmd == "sq":
        text, markup = v.squad_view(world, int(parts[1]))
    elif cmd == "pl":
        pid = int(parts[1])
        if pid not in world.players or world.players[pid].club_id != world.club_id:
            text, markup = v.squad_view(world, 0)
        else:
            text, markup = v.player_card(world, pid, mine=True)
    elif cmd == "pa":
        action, pid = parts[1], int(parts[2])
        fn = {"rest": tr.toggle_rest, "list": tr.toggle_list, "renew": tr.renew, "rel": tr.release,
              "qs": tr.quick_sell}[action]
        if pid not in world.players or world.players[pid].club_id != world.club_id:
            ok, alert = False, "Гравця вже немає в клубі."
        else:
            ok, alert = fn(world, pid)
        changed = ok
        if pid in world.players and world.players[pid].club_id == world.club_id:
            text, markup = v.player_card(world, pid, mine=True)
        else:
            text, markup = v.squad_view(world, 0)
    elif cmd == "xi":
        text, markup = v.lineup_view(world)
    elif cmd == "tac":
        text, markup = v.tactics_view(world)
    elif cmd == "tf":
        if parts[1] in FORMATIONS:
            world.club.formation = parts[1]
            changed = True
        text, markup = v.tactics_view(world)
    elif cmd == "ts":
        if parts[1] in STYLES:
            world.club.style = parts[1]
            changed = True
        text, markup = v.tactics_view(world)
    elif cmd == "trn":
        text, markup = v.training_view(world)
    elif cmd == "tt":
        if parts[1] in TRAINING:
            world.training = parts[1]
            changed = True
        text, markup = v.training_view(world)
    elif cmd == "tb":
        text, markup = v.table_view(world, int(parts[1]))
    elif cmd == "tbm":
        text, markup = v.table_view(world, world.club.division)
    elif cmd == "sc":
        text, markup = v.scorers_view(world, int(parts[1]))
    elif cmd == "fx":
        text, markup = v.fixtures_view(world)
    elif cmd == "tr":
        text, markup = v.transfers_view(world)
    elif cmd == "mk":
        text, markup = v.market_view(world, parts[1], int(parts[2]))
    elif cmd == "mp":
        pid = int(parts[1])
        if pid in world.players and world.players[pid].club_id != world.club_id:
            text, markup = v.player_card(world, pid, mine=False)
        else:
            text, markup = v.transfers_view(world)
    elif cmd == "buy":
        ok, alert = tr.buy(world, int(parts[1]))
        changed = ok
        if ok:
            text, markup = v.player_card(world, int(parts[1]), mine=True)
        else:
            text, markup = None, None
    elif cmd == "of":
        text, markup = v.offers_view(world)
    elif cmd in ("oa", "or"):
        ok, alert = (tr.accept_offer if cmd == "oa" else tr.reject_offer)(world, int(parts[1]))
        changed = ok
        text, markup = v.offers_view(world)
    elif cmd == "fin":
        text, markup = v.finance_view(world)
    elif cmd == "tp":
        c = world.club
        c.ticket_price = max(3, min(100, c.ticket_price + (1 if parts[1] == "+" else -1)))
        changed = True
        text, markup = v.finance_view(world)
    elif cmd == "up":
        ok, alert = tr.upgrade(world, parts[1])
        changed = ok
        text, markup = v.finance_view(world)
    elif cmd == "club":
        text, markup = v.club_view(world)
    elif cmd == "news":
        text, markup = v.news_view(world)

    if alert:
        await cq.answer(alert, show_alert=len(alert) > 60)
    else:
        await cq.answer()
    if text:
        await show(cq, text, markup)
    return changed


async def play_match(cq: CallbackQuery, world: World, live: bool) -> None:
    if season_over(world):
        await show(cq, "🏁 Усі тури зіграно!", v.kb([[("🏁 Підсумки сезону", "endseason")]]))
        return
    res = play_round(world, random.Random())
    if res is None:
        await show(cq, "Матчу немає.", v.kb([v.back()]))
        return
    msg = cq.message
    if live:
        for minute in LIVE_STEPS:
            try:
                await msg.edit_text(v.live_text(world, res, minute))
            except TelegramBadRequest:
                pass
            await asyncio.sleep(LIVE_DELAY if minute != 45 else LIVE_DELAY * 1.5)
    text = v.report_text(world, res)
    if world.fired:
        text += "\n\n🚪 <b>Правління звільнило тебе після цієї поразки.</b>"
        markup = v.kb([[("🔄 Нова кар’єра", "newyes")]])
    elif season_over(world):
        markup = v.kb([[("🏁 Підсумки сезону", "endseason")]])
    else:
        markup = v.after_match_kb()
    try:
        await msg.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await msg.answer(text, reply_markup=markup)


@router.message()
async def fallback(msg: Message) -> None:
    await msg.answer("Користуйся кнопками або командою /menu 🙂")
