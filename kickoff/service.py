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

    def play(self, w, prof: Profile, rng: random.Random | None = None) -> dict | None:
        if season_over(w):
            return None
        res = play_round(w, rng or random.Random())
        if res:
            home = res["home"] == w.club_id
            gf, ga = (res["hg"], res["ag"]) if home else (res["ag"], res["hg"])
            res["xp"] = prof.on_match(gf, ga)
        return res

    def finish_season(self, w, prof: Profile) -> dict:
        club_id = w.club_id
        summary = end_season(w, random.Random())
        summary["xp"] = prof.on_season(summary, club_id)
        return summary

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

    # convenience re-exports for handlers
    tr = tr
