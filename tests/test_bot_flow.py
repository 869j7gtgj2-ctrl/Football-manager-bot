"""Clicks through every screen of the bot with stub Telegram objects."""
import asyncio
import random
import re

from kickoff.bot import handlers
from kickoff.storage import Storage


class User:
    id = 42
    first_name = "Ілля"
    username = "illia"


class Msg:
    def __init__(self):
        self.texts = []
        self.markup = None

    async def edit_text(self, text, reply_markup=None):
        self.texts.append(text)
        self.markup = reply_markup or self.markup

    async def answer(self, text, reply_markup=None):
        self.texts.append(text)
        self.markup = reply_markup or self.markup


class CQ:
    def __init__(self, data, msg):
        self.data, self.message, self.from_user = data, msg, User()
        self.alerts = []

    async def answer(self, text=None, show_alert=False):
        if text:
            self.alerts.append(text)


def buttons(msg):
    return [b.callback_data for row in msg.markup.inline_keyboard for b in row] if msg.markup else []


async def click(data, msg):
    cq = CQ(data, msg)
    if data.startswith("pick:"):
        await handlers.cb_pick(cq)
    elif data.startswith("cc:"):
        await handlers.cb_choose_club(cq)
    elif data in ("newyes",):
        await handlers.cb_newyes(cq)
    elif data in ("pickdiv",):
        await handlers.cb_pickdiv(cq)
    elif data == "hall":
        await handlers.cb_hall(cq)
    elif data == "noop":
        await handlers.cb_noop(cq)
    elif data == "newask":
        await handlers.cb_newask(cq)
    else:
        await handlers.cb_game(cq)
    return cq


def test_click_everything(tmp_path):
    handlers.setup(Storage(str(tmp_path / "t.db")))
    handlers.LIVE_DELAY = 0
    random.seed(7)

    async def run():
        msg = Msg()
        await handlers.begin_new(msg, User())
        await click("pick:2", msg)
        club = next(b for b in buttons(msg) if b.startswith("cc:"))
        await click(club, msg)
        assert "головний тренер" in msg.texts[-1]
        # visit every menu screen and every button one level deep
        seen = set()
        for top in ["sq:0", "xi", "tac", "tb:2", "tb:1", "sc:2", "fx", "tr", "of", "trn", "fin", "club", "news",
                    "mk:FW:0", "mk:FA:0", "mk:YT:0", "nx"]:
            await click(top, msg)
            for b in buttons(msg):
                if b in seen or b.startswith(("play", "newyes", "pa:rel", "pa:qs", "newask")):
                    continue
                seen.add(b)
                await click(b, msg)
                await click(top, msg)
        # sign a free agent and list a player
        await click("mk:FA:0", msg)
        fa = next(b for b in buttons(msg) if b.startswith("mp:"))
        await click(fa, msg)
        await click("buy:" + fa.split(":")[1], msg)
        await click("sq:0", msg)
        pl = next(b for b in buttons(msg) if b.startswith("pl:"))
        await click(pl, msg)
        await click("pa:list:" + pl.split(":")[1], msg)
        # play two full seasons with live and fast modes
        for season in range(2):
            for i in range(22):
                await click("nx", msg)
                await click("play:live" if i % 5 == 0 else "play:fast", msg)
                assert re.search(r"\d+:\d+", msg.texts[-1])
                if "of" in buttons(msg):
                    pass
            await click("endseason", msg)
            assert "завершено" in msg.texts[-1]
            await click("m", msg)
        await click("of", msg)
        oa = [b for b in buttons(msg) if b.startswith("oa:")]
        if oa:
            await click(oa[0], msg)
        await click("hall", msg)
        assert "Зала слави" in msg.texts[-1]
    asyncio.run(run())
