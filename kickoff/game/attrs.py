"""Player attributes and traits, derived deterministically from skill, role, age and the player's id."""
from __future__ import annotations

import random
from functools import lru_cache

OUT = ("pac", "sho", "pas", "dri", "def", "phy")
GK = ("div", "ref", "han", "one", "kic", "pos")
NAMES = {"pac": "Швидкість", "sho": "Удар", "pas": "Пас", "dri": "Дриблінг", "def": "Захист", "phy": "Фізика",
         "div": "Стрибок", "ref": "Реакція", "han": "Гра руками", "one": "Вихід 1-на-1", "kic": "Гра ногами",
         "pos": "Позиція"}

BIAS = {
    "ST": (2, 6, -6, 1, -25, 2), "CF": (0, 4, 0, 4, -22, -2), "LW": (8, 0, -2, 6, -24, -8),
    "RW": (8, 0, -2, 6, -24, -8), "CAM": (-2, 1, 6, 5, -16, -8), "CM": (-4, -4, 5, 1, -2, 0),
    "CDM": (-6, -10, 2, -5, 6, 4), "LM": (5, -4, 2, 3, -8, -4), "RM": (5, -4, 2, 3, -8, -4),
    "CB": (-8, -25, -8, -15, 7, 6), "LB": (5, -18, -3, -4, 3, -1), "RB": (5, -18, -3, -4, 3, -1),
    "LWB": (6, -14, 0, 0, 0, -2), "RWB": (6, -14, 0, 0, 0, -2), "GK": (2, 3, 0, -2, -6, 1),
}
DEFAULT_ROLE = {"GK": "GK", "DF": "CB", "MF": "CM", "FW": "ST"}


@lru_cache(maxsize=50_000)
def _calc(pid: int, skill: int, role: str, pos: str, age: int) -> tuple:
    rng = random.Random(pid * 7919 + 17)
    bias = BIAS.get(role) or BIAS[DEFAULT_ROLE.get(pos, "CM")]
    out = []
    for i, b in enumerate(bias):
        v = skill + b + rng.uniform(-5, 5)
        if pos != "GK" and i == 0:
            v += 3 if age <= 21 else -6 if age >= 31 else -2 if age >= 28 else 0
        if pos != "GK" and i == 5:
            v += 2 if 26 <= age <= 31 else -3 if age <= 19 else 0
        out.append(int(max(20, min(99, round(v)))))
    return tuple(out)


def attributes(p) -> dict:
    keys = GK if p.pos == "GK" else OUT
    return dict(zip(keys, _calc(p.id, p.skill, p.role or "", p.pos, p.age)))


def factor(p, key: str) -> float:
    """Multiplier for match events, ~1.0 for an attribute equal to the player's skill."""
    a = attributes(p)
    v = a.get(key)
    return 1.0 if v is None else max(0.35, (v / max(30, p.skill)) ** 2)


TRAITS = [("pac", 84, "⚡ Блискавка"), ("sho", 84, "🎯 Снайпер"), ("pas", 84, "🧠 Диспетчер"),
          ("dri", 84, "🪄 Технар"), ("def", 84, "🧱 Стіна"), ("phy", 84, "💪 Танк"),
          ("ref", 84, "🐱 Кішка"), ("one", 84, "🧤 Майстер 1-на-1"), ("kic", 78, "🦶 Воротар-плеймейкер")]


def traits(p) -> list[str]:
    a = attributes(p)
    out = [t for k, lim, t in TRAITS if a.get(k, 0) >= lim]
    out.sort(key=lambda t: -a[[k for k, _, x in TRAITS if x == t][0]])
    out = out[:2]
    if p.age <= 20 and p.potential >= 84:
        out.append("🌟 Вундеркінд")
    if p.age >= 33:
        out.append("🧓 Ветеран")
    rng = random.Random(p.id * 31 + 5)
    if p.age >= 27 and rng.random() < 0.22:
        out.append("👑 Лідер")
    elif rng.random() < 0.12:
        out.append(rng.choice(["🔥 Великі матчі", "🧊 Холодний розум", "🏃 Невтомний", "🎭 Улюбленець фанів"]))
    return out[:4]


def profile(p) -> dict:
    a = attributes(p)
    return {"attrs": [{"key": k, "name": NAMES[k], "v": v} for k, v in a.items()], "traits": traits(p)}
