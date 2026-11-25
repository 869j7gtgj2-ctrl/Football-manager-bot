"""Telegram chat side: launches the Mini App."""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from ..game.leagues import LEAGUES
from ..game.season import table
from ..storage import Storage
from .messages import welcome

router = Router()
storage: Storage | None = None
webapp_url: str | None = None

def setup(st: Storage, url: str | None) -> Router:
    global storage, webapp_url
    storage, webapp_url = st, url
    return router


def play_kb(extra: bool = False, daily: bool = False) -> InlineKeyboardMarkup | None:
    rows = []
    if webapp_url:
        rows.append([InlineKeyboardButton(text="🎮 Грати", web_app=WebAppInfo(url=webapp_url))])
    if extra:
        row = [InlineKeyboardButton(text="🏅 Зала слави", callback_data="hall")]
        if daily:
            row.insert(0, InlineKeyboardButton(text="🎁 Забрати бонус", callback_data="daily"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def career_info(uid: int) -> dict | None:
    w = storage.load(uid)
    if not w or w.club_id not in w.clubs:
        return None
    rows = table(w, w.club.division)
    pos = [r["club"] for r in rows].index(w.club_id) + 1
    return {"club": w.club.name, "league": LEAGUES[w.club.division]["short"],
            "season": f"{2025 + w.season}/{str(2026 + w.season)[-2:]}", "position": pos, "of": len(rows),
            "points": rows[pos - 1]["pts"]}


def sync_profile(user):
    p = storage.profile(user.id)
    name = " ".join(x for x in (user.first_name, user.last_name) if x) or p.name
    if (p.name, p.username) != (name, user.username or ""):
        p.name, p.username = name, user.username or ""
        storage.save_profile(p)
    return p


@router.message(CommandStart())
@router.message(Command("play"))
async def cmd_start(msg: Message) -> None:
    p = sync_profile(msg.from_user)
    text = welcome(p, career_info(msg.from_user.id))
    if not webapp_url:
        text += "\n\n⚠️ Mini App ще не налаштований: потрібно додати публічний домен у Railway."
    await msg.answer(text, reply_markup=play_kb(extra=True, daily=p.daily_available()))


@router.callback_query(F.data == "daily")
async def cb_daily(cq: CallbackQuery) -> None:
    p = storage.profile(cq.from_user.id)
    ok, text, _ = p.claim_daily()
    storage.save_profile(p)
    await cq.answer(("🎉 " if ok else "") + text, show_alert=True)
    if ok:
        await cq.message.edit_text(welcome(p, career_info(cq.from_user.id)), reply_markup=play_kb(extra=True))


@router.callback_query(F.data == "hall")
async def cb_hall(cq: CallbackQuery) -> None:
    await cq.answer()
    await cmd_top(cq.message)


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
