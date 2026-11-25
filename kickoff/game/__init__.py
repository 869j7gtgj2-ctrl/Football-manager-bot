"""Game engine (pure Python, no Telegram dependency)."""
import random

from .generator import new_world
from .season import start_season


def start_career(world, club_id: int, rng: random.Random | None = None):
    rng = rng or random.Random()
    for c in world.clubs.values():
        c.is_user = c.id == club_id
    world.club_id = club_id
    world.confidence = 60
    world.fired = False
    start_season(world, rng)
    return world
