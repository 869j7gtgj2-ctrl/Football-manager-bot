"""Telegram chat side: launches the Mini App."""
from __future__ import annotations

from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from ..storage import Storage

router = Router()
storage: Storage | None = None
webapp_url: str | None = None

WELCOME = (
    "⚽ <b>KICKOFF · футбольний менеджер</b>\n\n"
    "Очоль справжній клуб з УПЛ, АПЛ, Ла Ліги, Бундесліги, Серії А, Ліги 1 чи Першої ліги. "
    "Склад, тактика, трансфери, фінанси, академія і матчі наживо.\n\n"
    "Натискай <b>Грати</b> 👇"
)


def setup(st: Storage, url: str | None) -> Router:
    global storage, webapp_url
    storage, webapp_url = st, url
    return router


def play_kb() -> InlineKeyboardMarkup | None:
    if not webapp_url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚽ Грати", web_app=WebAppInfo(url=webapp_url))]])


@router.message(CommandStart())
@router.message(Command("play"))
async def cmd_start(msg: Message) -> None:
    kb = play_kb()
    text = WELCOME if kb else WELCOME + "\n\n⚠️ Mini App ще не налаштований: власнику бота потрібно додати публічний домен у Railway."
    await msg.answer(text, reply_markup=kb)


@router.message(Command("top"))
async def cmd_top(msg: Message) -> None:
    rows = storage.top(10)
    if not rows:
        await msg.answer("🏅 <b>Зала слави</b>\n\nПоки порожньо. Стань першим!", reply_markup=play_kb())
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏅 <b>Зала слави</b>\n"]
    for i, (mgr, club, seasons, titles, promos, score) in enumerate(rows):
        lines.append(f"{medals[i] if i < 3 else f'{i + 1}.'} {escape(mgr)} ({escape(club)}) · {score} очк. · 🏆{titles}")
    await msg.answer("\n".join(lines), reply_markup=play_kb())


@router.message()
async def fallback(msg: Message) -> None:
    await msg.answer("Гра відкривається кнопкою «Грати» 👇", reply_markup=play_kb())
