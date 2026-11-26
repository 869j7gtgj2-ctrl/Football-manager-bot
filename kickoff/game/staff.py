"""Coaching staff: assistant, physio, fitness coach and scout. Each has a level 1..5 and a weekly wage."""
from __future__ import annotations

import random

from .leagues import LEAGUES
from .models import World
from .names import flag, random_name, random_nation

ROLES = {
    "assistant": ("🧠", "Асистент тренера", "Прискорює розвиток гравців: +8% до прогресу за кожен рівень."),
    "fitness": ("💪", "Фітнес-тренер", "Гравці швидше відновлюють сили між матчами: +3 форми за рівень."),
    "physio": ("🩺", "Лікар", "Скорочує травми: −15% тривалості за рівень, рідше травмуються."),
    "scout": ("🔭", "Скаут", "Знаходить таланти на ринку і підсилює набори в академію."),
}
MAX_LEVEL = 5


def _scale(w: World) -> float:
    return max(0.25, LEAGUES[w.club.division]["money"])


def wage(w: World, level: int) -> int:
    return int(level * level * 1800 * _scale(w) / 50) * 50


def hire_fee(w: World, level: int) -> int:
    return int(level * level * 60_000 * _scale(w) / 5000) * 5000


def level(w: World, role: str) -> int:
    s = w.staff.get(role)
    return s["level"] if s else 0


def candidates(w: World, rng: random.Random | None = None) -> dict:
    """Three candidates per role; refreshed each season (or when missing)."""
    key = f"s{w.season}"
    if w.staff_market.get("key") == key and w.staff_market.get("roles"):
        return w.staff_market["roles"]
    rng = rng or random.Random(w.user_id * 31 + w.season)
    nation = LEAGUES[w.club.division].get("nation", "UA")
    out = {}
    for role in ROLES:
        cur = level(w, role)
        lo, hi = max(1, cur), min(MAX_LEVEL, cur + 2)
        lv = sorted(rng.randint(lo, hi) for _ in range(3))
        out[role] = []
        for i, l in enumerate(lv):
            nat = nation if rng.random() < 0.6 else random_nation(rng, nation)
            out[role].append({"id": f"{role}{i}", "name": random_name(rng, nat), "nation": nat, "level": l,
                              "age": rng.randint(34, 64)})
    w.staff_market = {"key": key, "roles": out}
    return out


def hire(w: World, role: str, cid: str) -> tuple[bool, str]:
    cands = candidates(w).get(role, [])
    c = next((x for x in cands if x["id"] == cid), None)
    if not c:
        return False, "Кандидата не знайдено."
    if c["level"] <= level(w, role):
        return False, "Цей фахівець не сильніший за твого."
    fee = hire_fee(w, c["level"])
    if w.club.budget < fee:
        return False, f"Не вистачає коштів: потрібно €{fee:,}.".replace(",", " ")
    w.club.budget -= fee
    w.season_finances["transfers_out"] += fee
    from .finance import book
    book(w, "staff", fee, f"Найм: {c['name']} ({ROLES[role][1].lower()})")
    w.staff[role] = {"name": c["name"], "nation": c["nation"], "level": c["level"], "age": c["age"]}
    w.staff_market["roles"][role] = [x for x in cands if x["id"] != cid]
    w.add_news(f"{ROLES[role][0]} {ROLES[role][1]} {c['name']} приєднався до штабу.")
    return True, f"{ROLES[role][0]} {c['name']} тепер у штабі (рівень {c['level']})."


def fire(w: World, role: str) -> tuple[bool, str]:
    s = w.staff.pop(role, None)
    if not s:
        return False, "Посада вже вакантна."
    return True, f"{s['name']} покинув клуб."


def staff_wages(w: World) -> int:
    return sum(wage(w, s["level"]) for s in w.staff.values())


def scout_picks(w: World) -> list:
    """Best value-for-money talents from other clubs; more and sharper with a better scout."""
    lv = level(w, "scout")
    if not lv:
        return []
    budget = max(w.club.budget, 1)
    pool = [p for p in w.players.values() if p.club_id != w.club_id and p.age <= 23
            and p.potential >= p.skill + 6 and p.value() <= budget * 1.2]
    rng = random.Random(w.user_id * 7 + w.season * 101 + w.round // 5)
    noise = {p.id: rng.uniform(-8, 8) / lv for p in pool}
    pool.sort(key=lambda p: -(p.potential + noise[p.id] - p.value() / max(budget, 1) * 4))
    return pool[:2 + lv * 2]


def describe(w: World) -> list[dict]:
    out = []
    for role, (icon, name, info) in ROLES.items():
        s = w.staff.get(role)
        out.append({"role": role, "icon": icon, "title": name, "info": info,
                    "member": ({**s, "flag": flag(s["nation"]), "wage": wage(w, s["level"])} if s else None)})
    return out
