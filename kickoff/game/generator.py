"""World and player generation."""
from __future__ import annotations

import random

from .models import Club, Player, World
from .names import CLUBS_D1, CLUBS_D2, random_name

SQUAD_TEMPLATE = {"GK": 3, "DF": 8, "MF": 8, "FW": 5}


def clamp(v: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(v))))


def club_level(rep: int) -> float:
    return 40 + rep * 0.4


def make_player(world: World, rng: random.Random, pos: str, level: float, club_id, age: int | None = None,
                youth: bool = False) -> Player:
    if age is None:
        age = clamp(rng.triangular(17, 35, 25), 17, 35)
    skill = rng.gauss(level, 5)
    if age <= 20:
        skill -= (21 - age) * 2.5
    if age >= 32:
        skill -= (age - 31) * 1.2
    skill = clamp(skill, 25, 92)
    growth = max(0.0, (25 - age) * rng.gauss(2.6, 1.2))
    potential = clamp(skill + growth + rng.uniform(0, 4), skill, 97)
    name, nation = random_name(rng)
    p = Player(id=world.new_id(), name=name, age=age, pos=pos, skill=skill, potential=potential,
               club_id=club_id, nation=nation, youth=youth)
    p.wage = p.fair_wage()
    p.contract = rng.randint(1, 4)
    p.morale = rng.randint(60, 80)
    return p


def fill_squad(world: World, rng: random.Random, club: Club) -> None:
    level = club_level(club.reputation)
    for pos, n in SQUAD_TEMPLATE.items():
        for _ in range(n):
            p = make_player(world, rng, pos, level, club.id)
            world.players[p.id] = p


def youth_player(world: World, rng: random.Random, club: Club) -> Player:
    pos = rng.choices(["GK", "DF", "MF", "FW"], weights=[1, 4, 4, 3])[0]
    level = club_level(club.reputation) - 12 + club.academy_level * 2.5
    p = make_player(world, rng, pos, level, club.id, age=rng.randint(16, 18), youth=True)
    p.potential = clamp(p.potential + rng.randint(0, 6) + club.academy_level * 2, p.skill, 97)
    p.wage = max(200, p.fair_wage() // 2)
    p.contract = 3
    return p


def refresh_free_agents(world: World, rng: random.Random, n: int = 30) -> None:
    for p in list(world.free_agents()):
        del world.players[p.id]
    for _ in range(n):
        pos = rng.choices(["GK", "DF", "MF", "FW"], weights=[1, 4, 4, 3])[0]
        p = make_player(world, rng, pos, rng.uniform(45, 68), None)
        world.players[p.id] = p


def new_world(user_id: int, manager: str, seed: int | None = None) -> World:
    rng = random.Random(seed)
    world = World(user_id=user_id, manager=manager, club_id=0)
    for div, table, (hi, lo) in ((1, CLUBS_D1, (86, 56)), (2, CLUBS_D2, (52, 30))):
        n = len(table)
        for i, (name, city, emoji) in enumerate(table):
            rep = clamp(hi - (hi - lo) * i / (n - 1) + rng.uniform(-3, 3), 20, 95)
            club = Club(
                id=world.new_id(), name=name, city=city, division=div, reputation=rep,
                budget=int(rep * rep * 900 // 10000 * 10000), stadium=int(3000 + rep * rep * 3) // 500 * 500,
                ticket_price=5 + rep // 8, emoji=emoji,
                formation=rng.choice(["4-4-2", "4-3-3", "4-2-3-1", "3-5-2", "4-5-1"]),
                style=rng.choice(["balanced", "balanced", "attacking", "defensive", "counter", "pressing"]),
                training_level=1 + rep // 30, academy_level=1 + rep // 30,
            )
            world.clubs[club.id] = club
            fill_squad(world, rng, club)
    refresh_free_agents(world, rng)
    return world
