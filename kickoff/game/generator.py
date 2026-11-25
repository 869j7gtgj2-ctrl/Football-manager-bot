"""World and player generation. Uses real squads from the cache when available."""
from __future__ import annotations

import datetime as dt
import random

from .leagues import CLUBS, LEAGUES
from .models import Club, Player, World
from .names import random_name, random_nation

SQUAD_TEMPLATE = {"GK": 3, "DF": 8, "MF": 8, "FW": 5}
SEASON_START_YEAR = 2026


def clamp(v: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(v))))


def club_level(rep: int) -> float:
    """Club reputation is expressed directly on the player skill scale."""
    return float(rep)


def league_nation(club: Club) -> str:
    return LEAGUES.get(club.division, {}).get("nation", "UA")


def age_skill_adjust(age: int) -> float:
    if age <= 18:
        return -9
    if age <= 20:
        return -5
    if age <= 22:
        return -2
    if age <= 30:
        return 1
    if age <= 32:
        return -1
    return -4


def make_player(world: World, rng: random.Random, pos: str, level: float, club_id, age: int | None = None,
                youth: bool = False, nation: str | None = None) -> Player:
    if age is None:
        age = clamp(rng.triangular(17, 35, 25), 17, 35)
    skill = clamp(rng.gauss(level, 4.5) + age_skill_adjust(age), 25, 92)
    growth = max(0.0, (25 - age) * rng.gauss(2.4, 1.1))
    potential = clamp(skill + growth + rng.uniform(0, 3), skill, 96)
    if nation is None:
        club = world.clubs.get(club_id) if club_id else None
        nation = random_nation(rng, league_nation(club) if club else "UA")
    p = Player(id=world.new_id(), name=random_name(rng, nation), age=age, pos=pos, skill=skill, potential=potential,
               club_id=club_id, nation=nation, youth=youth)
    p.wage = p.fair_wage()
    p.contract = rng.randint(1, 4)
    p.morale = rng.randint(60, 80)
    return p


def fill_squad(world: World, rng: random.Random, club: Club) -> None:
    for pos, n in SQUAD_TEMPLATE.items():
        for _ in range(n):
            p = make_player(world, rng, pos, club.reputation - 3, club.id)
            world.players[p.id] = p


def age_from_dob(dob: str | None, rng: random.Random) -> int:
    if dob:
        try:
            born = dt.date.fromisoformat(dob[:10])
            ref = dt.date(SEASON_START_YEAR, 9, 1)
            return max(16, min(42, ref.year - born.year - ((ref.month, ref.day) < (born.month, born.day))))
        except ValueError:
            pass
    return clamp(rng.triangular(18, 34, 26), 17, 36)


def real_squad(world: World, rng: random.Random, club: Club, squad: list[dict], stars: dict) -> None:
    """Create Player objects from a cached real squad, estimating ability where no rating is known."""
    from ..stars import lookup  # local import to avoid cycles
    for entry in squad[:32]:
        age = age_from_dob(entry.get("dob"), rng)
        pos = entry.get("pos") or "MF"
        known = lookup(entry["name"], stars)
        if known:
            skill = known
        else:
            num = entry.get("number") or 0
            bonus = 2 if 1 <= num <= 11 else (-3 if num >= 40 else 0)
            skill = clamp(rng.gauss(club.reputation - 1.5, 3.5) + age_skill_adjust(age) + bonus, 30, 90)
        growth = max(0.0, (25 - age) * rng.gauss(2.2, 1.0))
        potential = clamp(skill + growth + rng.uniform(0, 3), skill, 96)
        p = Player(id=world.new_id(), name=entry["name"], age=age, pos=pos, skill=skill, potential=potential,
                   club_id=club.id, nation=entry.get("nation") or league_nation(club), real=True,
                   number=entry.get("number") or 0)
        p.wage = p.fair_wage()
        p.contract = rng.randint(1, 4)
        p.morale = rng.randint(62, 82)
        world.players[p.id] = p
    # make sure the squad is playable
    counts = {k: 0 for k in SQUAD_TEMPLATE}
    for p in world.squad(club.id):
        counts[p.pos] += 1
    need = {"GK": 2, "DF": 6, "MF": 6, "FW": 3}
    for pos, n in need.items():
        for _ in range(max(0, n - counts[pos])):
            p = make_player(world, rng, pos, club.reputation - 4, club.id)
            world.players[p.id] = p


def youth_player(world: World, rng: random.Random, club: Club) -> Player:
    pos = rng.choices(["GK", "DF", "MF", "FW"], weights=[1, 4, 4, 3])[0]
    level = club.reputation - 12 + club.academy_level * 2.5
    nation = league_nation(club) if rng.random() < 0.8 else random_nation(rng, league_nation(club))
    p = make_player(world, rng, pos, level, club.id, age=rng.randint(16, 18), youth=True, nation=nation)
    p.potential = clamp(p.potential + rng.randint(0, 6) + club.academy_level * 2, p.skill, 96)
    p.wage = max(300, p.fair_wage() // 2)
    p.contract = 3
    return p


def refresh_free_agents(world: World, rng: random.Random, n: int = 40) -> None:
    for p in list(world.free_agents()):
        if not p.real or p.age >= 33:
            del world.players[p.id]
    for _ in range(n):
        pos = rng.choices(["GK", "DF", "MF", "FW"], weights=[1, 4, 4, 3])[0]
        nation = rng.choice(["UA", "UA", "BR", "ES", "FR", "EN", "DE", "IT", "AR", "PT", "HR", "SN", "PL", "NL"])
        p = make_player(world, rng, pos, rng.uniform(52, 72), None, nation=nation)
        world.players[p.id] = p


def setup_finances(world: World, club: Club, rng: random.Random) -> None:
    money = LEAGUES[club.division]["money"]
    wages = sum(p.wage for p in world.squad(club.id))
    club.sponsor = int(wages * rng.uniform(0.62, 0.72))
    club.ticket_price = int(max(5, 6 + (club.reputation - 55) * 0.9 * (0.6 + money / 4)))
    gate_target = wages * 0.75
    club.stadium = int(max(3000, min(90000, gate_target / (club.ticket_price * 0.85))) // 500 * 500)
    club.budget = int(wages * rng.uniform(14, 22) * (0.8 + money / 10)) // 100_000 * 100_000


def new_world(user_id: int, manager: str, seed: int | None = None, real: dict | None = None,
              stars: dict | None = None) -> World:
    """real: {club_key: {"squad": [...], "crest": url}} from the cache."""
    rng = random.Random(seed)
    real = real or {}
    stars = stars or {}
    world = World(user_id=user_id, manager=manager, club_id=0)
    for lid, clubs in CLUBS.items():
        for name, city, level, colors, key in clubs:
            club = Club(
                id=world.new_id(), name=name, city=city, division=lid, reputation=level, budget=0, stadium=0,
                emoji="", colors=list(colors), key=key, country=LEAGUES[lid]["country"],
                formation=rng.choice(["4-4-2", "4-3-3", "4-2-3-1", "3-5-2", "4-5-1", "4-3-3", "4-2-3-1"]),
                style=rng.choice(["balanced", "balanced", "attacking", "defensive", "counter", "pressing"]),
                training_level=max(1, min(5, (level - 50) // 8)), academy_level=max(1, min(5, (level - 50) // 8)),
            )
            world.clubs[club.id] = club
            data = real.get(key)
            if data and data.get("crest"):
                club.crest = data["crest"]
            if data and len(data.get("squad") or []) >= 14:
                real_squad(world, rng, club, data["squad"], stars)
            else:
                fill_squad(world, rng, club)
            setup_finances(world, club, rng)
    refresh_free_agents(world, rng)
    return world
