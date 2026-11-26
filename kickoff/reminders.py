"""Gentle bot reminders: at most one message a day, only to keep a daily-bonus streak alive."""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
from zoneinfo import ZoneInfo

from .meta import today

log = logging.getLogger("kickoff.reminders")
KYIV = ZoneInfo("Europe/Kyiv")


def due(prof, now: dt.datetime) -> str | None:
    """Text to send, or None. Evening Kyiv time, streak of 2+ days that would break tomorrow."""
    if not 18 <= now.astimezone(KYIV).hour < 21:
        return None
    if prof.reminded == today() or not prof.daily_available() or prof.daily_streak < 2:
        return None
    if not prof._streak_continues():
        return None
    nxt = prof.daily_amount()
    return (f"🔥 Твоя серія {prof.daily_streak} дн. згорить уночі!\n"
            f"Забери щоденний бонус (+{nxt} монет) і зіграй тур, команда чекає.")


async def loop(svc, every: int = 1800) -> None:
    while True:
        try:
            now = dt.datetime.now(dt.timezone.utc)
            for prof in svc.st.all_profiles():
                text = due(prof, now)
                if text:
                    prof.reminded = today()
                    svc.st.save_profile(prof)
                    await svc.send(prof.user_id, text)
                    await asyncio.sleep(0.2)
        except Exception:  # never let reminders crash the bot
            log.exception("reminder loop failed")
        await asyncio.sleep(every)
