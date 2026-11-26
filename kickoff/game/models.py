"""Core data model. A whole career (world) is serialised to JSON per user."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Optional

POSITIONS = ("GK", "DF", "MF", "FW")
POS_UA = {"GK": "ВР", "DF": "ЗХ", "MF": "ПЗ", "FW": "НП"}
POS_NAME = {"GK": "Воротарі", "DF": "Захисники", "MF": "Півзахисники", "FW": "Нападники"}

from .roles import FORMATIONS  # noqa: E402  (real-football formations with pitch slots)

STYLES = {
    "attacking": "Атакувальний",
    "balanced": "Збалансований",
    "defensive": "Оборонний",
    "counter": "Контратаки",
    "pressing": "Пресинг",
}

TRAINING = {
    "balanced": "Збалансоване",
    "attack": "Атака",
    "defense": "Оборона",
    "fitness": "Фізпідготовка",
    "youth": "Розвиток молоді",
}

SQUAD_MAX = 30
SQUAD_MIN = 16


@dataclass
class Player:
    id: int
    name: str
    age: int
    pos: str
    skill: int
    potential: int
    club_id: Optional[int]
    nation: str = "UA"
    fitness: int = 100
    morale: int = 70
    wage: int = 0
    contract: int = 2
    injured: int = 0
    suspended: int = 0
    yellows: int = 0
    apps: int = 0
    goals: int = 0
    assists: int = 0
    rating_sum: float = 0.0
    listed: bool = False
    resting: bool = False
    youth: bool = False
    career_goals: int = 0
    career_apps: int = 0
    real: bool = False
    number: int = 0
    role: str = ""
    ask: int = 0          # asking price when the user lists the player
    trained: int = -1     # season*1000+round of the last paid individual training
    loan: int = 0         # parent club id while the player is out on loan (0 = not on loan)

    @property
    def avg_rating(self) -> float:
        return round(self.rating_sum / self.apps, 2) if self.apps else 0.0

    @property
    def available(self) -> bool:
        return self.injured == 0 and self.suspended == 0

    def value(self) -> int:
        base = 100_000 * math.exp((self.skill - 50) / 6.0)
        gap = max(0, self.potential - self.skill)
        if self.age <= 23:
            base *= 1 + gap * 0.035
        if self.age >= 33:
            base *= 0.35
        elif self.age >= 30:
            base *= 0.65
        elif self.age >= 28:
            base *= 0.85
        if self.pos == "GK":
            base *= 0.8
        if base >= 1_000_000:
            return int(round(base / 100_000.0) * 100_000)
        return int(round(base / 5000.0) * 5000) or 5000

    def fair_wage(self) -> int:
        w = max(400.0, 100_000 * math.exp((self.skill - 50) / 6.0) * 0.0022)
        return int(round(w / 50.0) * 50)


@dataclass
class Club:
    id: int
    name: str
    city: str
    division: int
    reputation: int
    budget: int
    stadium: int
    ticket_price: int = 10
    formation: str = "4-4-2"
    style: str = "balanced"
    training_level: int = 1
    academy_level: int = 1
    is_user: bool = False
    emoji: str = "⚽"
    colors: list = field(default_factory=lambda: ["#3b82f6", "#ffffff"])
    key: str = ""
    sponsor: int = 0
    crest: str = ""
    country: str = ""


@dataclass
class MatchResult:
    round: int
    division: int
    home: int
    away: int
    hg: int
    ag: int


@dataclass
class Offer:
    id: int
    player_id: int
    club_id: int
    fee: int
    kind: str = "bid"  # bid for user player; "final" after one counter
    max_fee: int = 0


@dataclass
class World:
    user_id: int
    manager: str
    club_id: int
    season: int = 1
    round: int = 0
    clubs: dict = field(default_factory=dict)
    players: dict = field(default_factory=dict)
    fixtures: dict = field(default_factory=dict)  # division -> list of rounds -> list[(h, a)]
    results: list = field(default_factory=list)
    training: str = "balanced"
    board_target: int = 6
    confidence: int = 60
    news: list = field(default_factory=list)
    offers: list = field(default_factory=list)
    trophies: list = field(default_factory=list)
    history: list = field(default_factory=list)
    last_match: Optional[dict] = None
    next_id: int = 1
    fired: bool = False
    slot: int = 0
    lineups: dict = field(default_factory=dict)  # "1"/"2" -> list of 11 player ids (None = auto) in slot order
    active_lineup: int = 1
    captain: Optional[int] = None
    last_xi: list = field(default_factory=list)
    cups: dict = field(default_factory=dict)  # "cup" / "ucl" -> competition state (see game/cups.py)
    euro_next: dict = field(default_factory=dict)
    negotiations: dict = field(default_factory=dict)  # player id (str) -> {"n": rounds, "counter": fee}
    pitches: list = field(default_factory=list)
    pending: dict = field(default_factory=dict)  # user's match paused at half-time (match.Sim state)
    press: dict = field(default_factory=dict)    # open post-match press conference
    records: dict = field(default_factory=dict)  # club records hub
    awards: list = field(default_factory=list)   # season awards history
    fin: dict = field(default_factory=dict)        # user's club money by category this season
    fin_history: list = field(default_factory=list)
    ledger: list = field(default_factory=list)     # notable operations
    sponsor: dict = field(default_factory=dict)    # current general sponsor contract
    sponsor_offers: list = field(default_factory=list)
    ballon: list = field(default_factory=list)     # Golden Ball history
    totw: dict = field(default_factory=dict)       # team of the week of the last league round
    staff: dict = field(default_factory=dict)  # role -> {"name","nation","level","age"}
    staff_market: dict = field(default_factory=dict)
    challenge: dict = field(default_factory=dict)  # weekly challenge progress for this career
    dilemmas: list = field(default_factory=list)  # player situations waiting for a decision  # agent proposals: {"id","pid","fee","until","note"}
    season_finances: dict = field(default_factory=lambda: {"income": 0, "wages": 0, "transfers_in": 0, "transfers_out": 0})

    # ---------- helpers ----------
    def new_id(self) -> int:
        self.next_id += 1
        return self.next_id

    @property
    def club(self) -> Club:
        return self.clubs[self.club_id]

    def squad(self, club_id: int) -> list[Player]:
        return [p for p in self.players.values() if p.club_id == club_id]

    def division_clubs(self, division: int) -> list[Club]:
        return [c for c in self.clubs.values() if c.division == division]

    def free_agents(self) -> list[Player]:
        return [p for p in self.players.values() if p.club_id is None]

    def add_news(self, text: str) -> None:
        self.news.insert(0, f"С{self.season} Т{self.round}: {text}")
        del self.news[30:]

    @property
    def rounds_total(self) -> int:
        return len(self.fixtures.get(self.club.division, []))

    def transfer_window_open(self) -> bool:
        total = self.rounds_total or 22
        mid = total // 2
        return self.round <= 2 or mid <= self.round <= mid + 2

    # ---------- serialisation ----------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["clubs"] = {str(k): asdict(v) for k, v in self.clubs.items()}
        d["players"] = {str(k): asdict(v) for k, v in self.players.items()}
        d["fixtures"] = {str(k): v for k, v in self.fixtures.items()}
        d["results"] = [asdict(r) for r in self.results]
        d["offers"] = [asdict(o) for o in self.offers]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "World":
        d = dict(d)
        clubs = {int(k): Club(**v) for k, v in d.pop("clubs").items()}
        players = {int(k): Player(**v) for k, v in d.pop("players").items()}
        fixtures = {int(k): [[tuple(m) for m in rnd] for rnd in v] for k, v in d.pop("fixtures").items()}
        results = [MatchResult(**r) for r in d.pop("results")]
        offers = [Offer(**o) for o in d.pop("offers")]
        w = cls(**d)
        w.clubs, w.players, w.fixtures, w.results, w.offers = clubs, players, fixtures, results, offers
        ensure_roles(w)
        return w


def ensure_roles(world: "World") -> None:
    """Old saves / generated players: give every player a real-football position."""
    import random as _r
    from .roles import assign_roles
    missing = [p for p in world.players.values() if not p.role]
    if not missing:
        return
    rng = _r.Random(world.user_id * 31 + world.season)
    by_club: dict = {}
    for p in missing:
        by_club.setdefault(p.club_id, []).append(p)
    for ps in by_club.values():
        assign_roles(ps, rng)
