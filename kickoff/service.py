"""Game service shared by the chat bot and the Mini App: careers, slots, rewards."""
from __future__ import annotations

import asyncio
import random
from collections import defaultdict

from .game import new_world, start_career
from .game import transfers as tr
from .game.season import end_season, play_round, season_over
from .meta import MAX_SLOTS, SHOP, Profile
from .stars import STARS
from .storage import Storage

locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
# careers being created (world generated, club not chosen yet): (user, slot) -> World
pending: dict[tuple[int, int], object] = {}


class Service:
    def __init__(self, storage: Storage):
        self.st = storage
        self.notify = None  # async callable(user_id, html_text) set by main.py when the bot runs

    async def send(self, uid: int, text: str) -> None:
        if self.notify:
            try:
                await self.notify(uid, text)
            except Exception:  # user may have blocked the bot; never break the game
                pass

    # ---------------------------------------------------------------- careers
    def draft_world(self, uid: int, slot: int, manager: str):
        w = new_world(uid, manager, real=self.st.real_all(), stars=STARS)
        w.slot = slot
        pending[(uid, slot)] = w
        return w

    def create_career(self, uid: int, slot: int, club_id: int, manager: str):
        prof = self.st.profile(uid)
        if slot >= prof.slots_unlocked or slot >= MAX_SLOTS:
            raise ValueError("Слот закритий")
        w = pending.pop((uid, slot), None) or self.draft_world(uid, slot, manager)
        pending.pop((uid, slot), None)
        if club_id not in w.clubs:
            raise ValueError("Клуб не знайдено")
        start_career(w, club_id)
        w.slot = slot
        w.add_news(f"🤝 {manager} очолив {w.club.name}!")
        self.st.save(w)
        prof.active_slot = slot
        self.st.save_profile(prof)
        return w

    def first_half(self, w, rng: random.Random | None = None):
        """Start the user's next match live: simulate to half-time and park it in w.pending."""
        from .game.match import Sim
        from .game.season import user_fixture
        if w.pending:
            return Sim.restore(w, w.pending["state"], rng or random.Random())
        fx = user_fixture(w)
        if not fx or season_over(w):
            return None
        sim = Sim(w, w.clubs[fx["home"]], w.clubs[fx["away"]], rng or random.Random(), detailed=True)
        sim.run(45, auto_subs_for=(0, 1))
        w.pending = {"state": sim.state(), "comp": fx["comp"]}
        return sim

    def second_half(self, w, prof: Profile, talk: str = "", style: str = "", subs: list | None = None,
                    rng: random.Random | None = None) -> dict | None:
        from .game.match import Sim
        from .game.models import STYLES
        rng = rng or random.Random()
        if not w.pending:
            return None
        sim = Sim.restore(w, w.pending["state"], rng)
        side = 0 if sim.home.id == w.club_id else 1
        if style in STYLES:
            w.club.style = style
        if talk:
            sim.team_talk(side, talk)
        for out_id, in_id in (subs or [])[:5]:
            sim.substitute_manual(side, int(out_id), int(in_id))
        sim.run(90, auto_subs_for=(1 - side,) if subs else (0, 1))
        res = sim.finish()
        w.pending = {}
        return self.play(w, prof, rng, user_res=res)

    def play(self, w, prof: Profile, rng: random.Random | None = None, user_res: dict | None = None) -> dict | None:
        if season_over(w):
            return None
        from .game.season import play_next
        if w.pending and user_res is None:  # a paused live match: finish it without changes
            return self.second_half(w, prof, rng=rng)
        res = play_next(w, rng or random.Random(), user_res)
        if res:
            home = res["home"] == w.club_id
            gf, ga = (res["hg"], res["ag"]) if home else (res["ag"], res["hg"])
            res["xp"] = prof.on_match(gf, ga)
            goals = [e for e in res.get("events", []) if e.get("type") == "goal"]
            first_against = bool(goals) and (goals[0]["side"] == 0) != home
            prof.on_weekly(gf, ga, first_against, bool(res.get("comp")))
            res["coins"] = prof.last_coins
            if res.get("home") in (w.club_id,) or res.get("away") == w.club_id:
                from .game import events as ev
                w.records.pop("_boost", None)
                res["records"] = ev.update_records(w, res)
                ev.open_press(w, res, rng)
                ev.maybe_dilemma(w, rng or random.Random())
                if gf > ga:
                    from .game import sponsors
                    sponsors.on_win(w)
        return res

    def finish_season(self, w, prof: Profile) -> dict:
        from .game.season import table
        club = w.club
        row = next(r for r in table(w, club.division) if r["club"] == club.id)
        squad = w.squad(club.id)
        top = max(squad, key=lambda p: (p.goals, p.assists), default=None)
        scorer = (top.name, top.goals) if top and top.goals else None
        star = max((p for p in squad if p.apps >= 5), key=lambda p: p.avg_rating, default=None)
        best = (star.name, star.avg_rating) if star else None
        season = w.season
        from .game.events import season_awards
        awards = season_awards(w)
        from .game.ballon import compute as ballon
        ball = ballon(w)
        summary = end_season(w, random.Random())
        summary["xp"] = prof.on_season(summary, club.id)
        summary["cups_won"] = [c["name"] for c in (summary.get("cups") or {}).values() if c.get("winner") == club.id]
        summary.update({
            "club": club.name, "season_label": f"{2025 + season}/{str(2026 + season)[-2:]}",
            "pts": row["pts"], "w": row["w"], "d": row["d"], "l": row["l"], "gf": row["gf"], "ga": row["ga"],
            "scorer": scorer, "best": best,
            "promoted_me": club.id in summary.get("promoted", []), "relegated_me": club.id in summary.get("relegated", []),
            "awards": awards, "ballon": ball, "confidence": w.confidence, "fired": w.fired, "new_target": w.board_target,
        })
        return summary

    # ---------------------------------------------------------------- friends
    def friends(self, uid: int) -> list[dict]:
        from .game.match import pick_lineup
        from .game.season import table
        out = []
        for p in self.st.all_profiles():
            w = self.st.load(p.user_id, p.active_slot)
            if w is None or w.club_id not in w.clubs:
                continue
            c = w.club
            rows = table(w, c.division)
            pos = next((i + 1 for i, r in enumerate(rows) if r["club"] == c.id), None)
            lu = pick_lineup(w, c, auto=True)
            wk = p.weekly_list() if p.weekly.get("week") else None
            out.append({"uid": p.user_id, "name": p.name, "level": p.rank[1], "rank": p.rank[0], "xp": p.xp,
                        "club": c, "world": w, "pos": pos, "season": w.season,
                        "rating": round(sum(x.skill for _, x in lu) / max(1, len(lu))),
                        "trophies": len([t for t in w.trophies if t.startswith("🏆")]),
                        "weekly": sum(1 for i in (wk or {}).get("items", []) if i["done"]),
                        "me": p.user_id == uid, "h2h": self.st.profile(uid).h2h.get(str(p.user_id))})
        out.sort(key=lambda x: (-x["xp"], x["uid"]))
        return out

    def friendly(self, uid: int, fid: int, rng: random.Random | None = None) -> tuple[bool, str, dict | None]:
        """Friendly between my active club and a friend's active club (each from its own world)."""
        import math
        from .game.match import TeamState, bench, expected_goals, pick_lineup, weighted_pick
        from .meta import today
        if uid == fid:
            return False, "Не можна зіграти з самим собою.", None
        rng = rng or random.Random()
        me, fr = self.st.profile(uid), self.st.profile(fid)
        w1, w2 = self.st.load(uid, me.active_slot), self.st.load(fid, fr.active_slot)
        if not w1 or not w2:
            return False, "У когось із вас немає активної кар’єри.", None
        rec = me.h2h.setdefault(str(fid), {"w": 0, "d": 0, "l": 0, "last": ""})
        if rec.get("last") == today():
            return False, "Сьогодні ви вже грали. Реванш завтра!", None
        teams = []
        for w in (w1, w2):
            lu = pick_lineup(w, w.club, auto=True)
            teams.append(TeamState(club=w.club, lineup=lu, bench=bench(w, w.club, lu)))
        s1, s2 = teams[0].strengths(), teams[1].strengths()
        x1, poss = expected_goals(s1, s2, True)
        x2, _ = expected_goals(s2, s1, False)

        def pois(lam):
            l, k, p = math.exp(-lam), 0, 1.0
            while True:
                p *= rng.random()
                if p <= l:
                    return k
                k += 1
        g1, g2 = pois(x1), pois(x2)
        goals = []
        for side, n in ((0, g1), (1, g2)):
            for _ in range(n):
                pl = weighted_pick(rng, teams[side].lineup, {"FW": 5, "MF": 2.5, "DF": 0.6, "GK": 0})
                goals.append({"min": rng.randint(1, 90), "side": side, "name": pl.name if pl else ""})
        goals.sort(key=lambda g: g["min"])
        res = "w" if g1 > g2 else "d" if g1 == g2 else "l"
        rec[res] += 1
        rec["last"] = today()
        coins = {"w": 8, "d": 4, "l": 2}[res]
        me.coins += coins
        frec = fr.h2h.setdefault(str(uid), {"w": 0, "d": 0, "l": 0, "last": ""})
        frec[{"w": "l", "l": "w", "d": "d"}[res]] += 1
        self.st.save_profile(me)
        self.st.save_profile(fr)
        out = {"home": w1.club, "away": w2.club, "hg": g1, "ag": g2, "goals": goals, "coins": coins,
               "possession": round(poss * 100), "xg": [round(x1, 2), round(x2, 2)], "rec": rec,
               "friend": fr.name, "friendUid": fid}
        return True, f"{w1.club.name} {g1}:{g2} {w2.club.name}", out

    # ---------------------------------------------------------------- shop
    def buy_item(self, w, prof: Profile, item: str) -> tuple[bool, str]:
        it = SHOP.get(item)
        if not it:
            return False, "Товар не знайдено."
        if prof.coins < it["price"]:
            return False, f"Потрібно {it['price']} монет."
        if w is None:
            return False, "Спершу почни кар’єру."
        squad = w.squad(w.club_id)
        if item == "sponsor":
            w.club.budget += 1_000_000
            w.season_finances["income"] += 1_000_000
            from .game.finance import book
            book(w, "owner", 1_000_000, "Спонсорський контракт з магазину")
        elif item == "medic":
            if not any(p.injured for p in squad):
                return False, "Травмованих немає."
            for p in squad:
                p.injured = 0
        elif item == "energy":
            for p in squad:
                p.fitness = 100
        elif item == "motivation":
            for p in squad:
                p.morale = min(100, p.morale + 20)
        elif item == "camp":
            xi = sorted((p for p in squad if p.skill < p.potential), key=lambda p: -p.skill)[:5]
            if not xi:
                return False, "Усі гравці вже на межі потенціалу."
            for p in xi:
                p.skill += 1
        elif item == "scout":
            if len(squad) >= 30:
                return False, "У складі вже 30 гравців."
            from .game.generator import youth_player
            y = youth_player(w, random.Random(), w.club)
            y.potential = max(y.potential, min(95, w.club.reputation + random.randint(8, 16)))
            w.players[y.id] = y
            w.add_news(f"🔭 Скаути знайшли талант: {y.name} (потенціал {y.potential}).")
        prof.coins -= it["price"]
        return True, f"{it['icon']} {it['title']}: готово!"

    def buy_premium(self, w, prof: Profile, item: str) -> tuple[bool, str]:
        from .meta import MAX_SLOTS as _MAX, PREMIUM, today
        it = PREMIUM.get(item)
        if not it:
            return False, "Товар не знайдено."
        if prof.gems < it["price"]:
            return False, f"Потрібно {it['price']} 💎. Поповнення кристалів з’явиться згодом."
        if item == "slot":
            if prof.slots_unlocked >= _MAX:
                return False, "Усі слоти вже відкрито."
            prof.slots_unlocked += 1
        elif item == "xp2":
            prof.xp_boost_until = today()
        elif item == "frame":
            if "gold_frame" in prof.cosmetics:
                return False, "Рамка вже твоя."
            prof.cosmetics.append("gold_frame")
        elif item in ("legend", "megasponsor"):
            if w is None:
                return False, "Спершу почни кар’єру."
            if item == "megasponsor":
                w.club.budget += 10_000_000
                w.season_finances["income"] += 10_000_000
                from .game.finance import book
                book(w, "owner", 10_000_000, "Генеральний інвестор (преміум)")
            else:
                if len(w.squad(w.club_id)) >= 30:
                    return False, "У складі вже 30 гравців."
                from .game.generator import youth_player
                y = youth_player(w, random.Random(), w.club)
                y.age = random.choice([16, 17])
                y.potential = random.randint(88, 94)
                y.skill = max(y.skill, min(72, w.club.reputation - 6))
                w.players[y.id] = y
                w.add_news(f"🌟 Легендарний скаут привів вундеркінда: {y.name} (потенціал {y.potential}).")
        prof.gems -= it["price"]
        return True, f"{it['icon']} {it['title']}: готово!"

    # convenience re-exports for handlers
    tr = tr
