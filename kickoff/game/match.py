"""Minute-by-minute match engine."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .models import Club, Player, World
from .roles import FORMATIONS, familiarity, line_of

STYLE_MODS = {
    #            att   mid   def   poss  fatigue
    "balanced": (1.00, 1.00, 1.00, 1.00, 0),
    "attacking": (1.07, 1.00, 0.94, 1.03, 2),
    "defensive": (0.92, 0.99, 1.07, 0.95, -2),
    "counter": (1.03, 0.97, 1.03, 0.90, 0),
    "pressing": (1.02, 1.06, 0.99, 1.05, 5),
}


def prole(p: Player) -> str:
    return p.role or {"GK": "GK", "DF": "CB", "MF": "CM", "FW": "ST"}.get(p.pos, "CM")


def slot_skill(p: Player, slot: str) -> float:
    return p.skill * familiarity(prole(p), slot)


def condition(p: Player) -> float:
    return (0.72 + 0.28 * p.fitness / 100) * (0.94 + 0.12 * p.morale / 100)


def formation_slots(club: Club) -> list[str]:
    return [r for r, _, _ in FORMATIONS.get(club.formation) or FORMATIONS["4-4-2"]]


def _auto_fill(slots: list[str], chosen: list, pool: list[Player]) -> list:
    """Global greedy assignment of the best available players to empty slots."""
    used = {p.id for p in chosen if p}
    pairs = []
    for i, slot in enumerate(slots):
        if chosen[i] is None:
            for p in pool:
                if p.id not in used:
                    pairs.append((slot_skill(p, slot) * condition(p), i, p))
    pairs.sort(key=lambda t: -t[0])
    for _, i, p in pairs:
        if chosen[i] is None and p.id not in used:
            chosen[i] = p
            used.add(p.id)
    return chosen


def available_pool(world: World, club: Club) -> list[Player]:
    pool = [p for p in world.squad(club.id) if p.available and not (club.is_user and p.resting)]
    if len(pool) < 11:  # emergency: use resting players too
        pool = [p for p in world.squad(club.id) if p.available]
    return pool


def pick_lineup(world: World, club: Club, auto: bool = False) -> list[tuple[str, Player]]:
    slots = formation_slots(club)
    pool = available_pool(world, club)
    chosen: list = [None] * len(slots)
    if club.is_user and club.id == world.club_id and not auto:
        ids = (world.lineups or {}).get(str(world.active_lineup)) or []
        ok = {p.id: p for p in pool}
        seen = set()
        for i, pid in enumerate(ids[:len(slots)]):
            if pid in ok and pid not in seen:
                chosen[i] = ok[pid]
                seen.add(pid)
    _auto_fill(slots, chosen, pool)
    return [(slots[i], p) for i, p in enumerate(chosen) if p is not None]


def chemistry(world: World, club: Club, lineup) -> int:
    """0-100: positional fit, settled XI and morale."""
    if not lineup:
        return 0
    fit = sum(familiarity(prole(p), s) for s, p in lineup) / len(lineup)
    if club.id == world.club_id and world.last_xi:
        last = set(world.last_xi)
        stable = sum(1 for _, p in lineup if p.id in last) / len(lineup)
    else:
        stable = 0.8
    morale = sum(p.morale for _, p in lineup) / len(lineup) / 100
    fit_score = max(0.0, (fit - 0.6) / 0.4)
    return round(100 * (0.6 * fit_score + 0.25 * stable + 0.15 * morale))


def chem_mult(chem: int) -> float:
    return 0.95 + 0.07 * chem / 100


def bench(world: World, club: Club, lineup) -> list[Player]:
    used = {p.id for _, p in lineup}
    pool = [p for p in world.squad(club.id) if p.available and p.id not in used]
    pool.sort(key=lambda p: p.skill * condition(p), reverse=True)
    return pool[:9]


@dataclass
class TeamState:
    club: Club
    lineup: list
    bench: list
    goals: int = 0
    shots: int = 0
    on_target: int = 0
    reds: int = 0
    subs: int = 0
    xg: float = 0.0
    ratings: dict = field(default_factory=dict)
    mult: float = 1.0

    def line(self, line: str) -> list[float]:
        return [slot_skill(p, s) * condition(p) * self.mult for s, p in self.lineup if line_of(s) == line]

    def strengths(self) -> dict:
        def avg(xs, default=30.0):
            return sum(xs) / len(xs) if xs else default
        gk, df, mf, fw = (self.line(s) for s in ("GK", "DF", "MF", "FW"))
        att_mod, mid_mod, def_mod, poss_mod, _ = STYLE_MODS.get(self.club.style, STYLE_MODS["balanced"])
        attack = avg(fw + [x * 0.8 for x in mf[:2]]) * (1 + 0.035 * (len(fw) - 2)) * att_mod
        midfield = avg(mf) * (1 + 0.035 * (len(mf) - 4)) * mid_mod
        defence = avg(df) * (1 + 0.035 * (len(df) - 4)) * def_mod
        keeper = avg(gk, 20.0)
        penalty = 1 - 0.12 * self.reds
        return {"att": attack * penalty, "mid": midfield * penalty * poss_mod, "def": defence * penalty,
                "gk": keeper}


def weighted_pick(rng: random.Random, lineup, weights: dict) -> Player | None:
    items = [(p, weights.get(line_of(s), 1) * max(p.skill, 1)) for s, p in lineup]
    if not items:
        return None
    total = sum(w for _, w in items)
    r = rng.uniform(0, total)
    for p, w in items:
        r -= w
        if r <= 0:
            return p
    return items[-1][0]


def expected_goals(a: dict, b: dict, home: bool) -> tuple[float, float]:
    poss = a["mid"] ** 2.2 / (a["mid"] ** 2.2 + b["mid"] ** 2.2)
    attack = a["att"] * 0.75 + a["mid"] * 0.25
    defence = b["def"] * 0.72 + b["gk"] * 0.28
    xg = 1.25 * (attack / defence) ** 2.6 * (0.55 + 0.9 * poss) * (1.12 if home else 0.93)
    return max(0.15, min(4.5, xg)), poss


TALKS = {  # half-time team talk -> (multiplier if losing, drawing, winning)
    "fire": (1.05, 1.03, 0.98),     # шалена мотивація
    "calm": (0.99, 1.01, 1.03),     # спокій і контроль
    "praise": (1.0, 1.02, 1.04),    # похвала
    "blame": (1.04, 0.99, 0.95),    # критика
}


class Sim:
    """Minute-by-minute match that can be paused (e.g. at half-time) and resumed, also across requests."""

    def __init__(self, world: World, home: Club, away: Club, rng: random.Random, detailed: bool = False):
        self.world, self.rng, self.detailed = world, rng, detailed
        self.home, self.away = home, away
        self.teams: list[TeamState] = []
        for c in (home, away):
            lu = pick_lineup(world, c)
            mult = chem_mult(chemistry(world, c, lu))
            if c.id == world.club_id and world.captain in {p.id for _, p in lu}:
                mult *= 1.01
            if c.id == world.club_id and world.records.get("_boost"):
                mult *= world.records["_boost"]  # press-conference effect; cleared after the user's match
            self.teams.append(TeamState(club=c, lineup=lu, bench=bench(world, c, lu), mult=mult))
        self.events: list[dict] = []
        self.yellows: dict[int, int] = {}
        self.poss_sum = 0.0
        self.minutes_played = {p.id: 0 for t in self.teams for _, p in t.lineup}
        self.xi = [[p.id for _, p in t.lineup] for t in self.teams]
        self.starts = {p.id: 0 for t in self.teams for _, p in t.lineup}
        self.goals_by: dict[int, int] = {}
        self.assists_by: dict[int, int] = {}
        self.injuries: list = []
        self.reds: list[int] = []
        self.minute = 0

    # ---------------------------------------------------------------- persistence
    def state(self) -> dict:
        return {"home": self.home.id, "away": self.away.id, "detailed": self.detailed, "minute": self.minute,
                "teams": [{"lineup": [[s, p.id] for s, p in t.lineup], "bench": [p.id for p in t.bench],
                           "goals": t.goals, "shots": t.shots, "on_target": t.on_target, "reds": t.reds,
                           "subs": t.subs, "xg": t.xg, "mult": t.mult} for t in self.teams],
                "events": self.events, "yellows": {str(k): v for k, v in self.yellows.items()},
                "poss_sum": self.poss_sum, "minutes_played": {str(k): v for k, v in self.minutes_played.items()},
                "xi": self.xi, "starts": {str(k): v for k, v in self.starts.items()},
                "goals_by": {str(k): v for k, v in self.goals_by.items()},
                "assists_by": {str(k): v for k, v in self.assists_by.items()},
                "injuries": self.injuries, "reds": self.reds}

    @classmethod
    def restore(cls, world: World, d: dict, rng: random.Random) -> "Sim":
        sim = cls.__new__(cls)
        sim.world, sim.rng, sim.detailed = world, rng, d["detailed"]
        sim.home, sim.away = world.clubs[d["home"]], world.clubs[d["away"]]
        P = world.players
        sim.teams = []
        for c, t in zip((sim.home, sim.away), d["teams"]):
            ts = TeamState(club=c, lineup=[(s, P[i]) for s, i in t["lineup"] if i in P],
                           bench=[P[i] for i in t["bench"] if i in P], mult=t["mult"])
            ts.goals, ts.shots, ts.on_target, ts.reds, ts.subs, ts.xg = (t["goals"], t["shots"], t["on_target"],
                                                                          t["reds"], t["subs"], t["xg"])
            sim.teams.append(ts)
        ik = lambda m: {int(k): v for k, v in m.items()}
        sim.events, sim.yellows, sim.poss_sum = d["events"], ik(d["yellows"]), d["poss_sum"]
        sim.minutes_played, sim.xi, sim.starts = ik(d["minutes_played"]), d["xi"], ik(d["starts"])
        sim.goals_by, sim.assists_by = ik(d["goals_by"]), ik(d["assists_by"])
        sim.injuries, sim.reds, sim.minute = [tuple(x) for x in d["injuries"]], d["reds"], d["minute"]
        return sim

    # ---------------------------------------------------------------- half-time decisions
    def team_talk(self, side: int, talk: str) -> None:
        t = self.teams[side]
        mine, opp = t.goals, self.teams[1 - side].goals
        k = TALKS.get(talk)
        if k:
            t.mult *= k[0] if mine < opp else k[1] if mine == opp else k[2]

    def substitute_manual(self, side: int, out_id: int, in_id: int) -> bool:
        t = self.teams[side]
        if t.subs >= 5:
            return False
        idx = next((i for i, (_, p) in enumerate(t.lineup) if p.id == out_id), None)
        repl = next((p for p in t.bench if p.id == in_id), None)
        if idx is None or repl is None:
            return False
        slot, out = t.lineup[idx]
        self.minutes_played[out.id] = self.minute - self.starts.get(out.id, 0)
        t.bench.remove(repl)
        t.lineup[idx] = (slot, repl)
        t.subs += 1
        self.starts[repl.id] = self.minute
        self.minutes_played.setdefault(repl.id, 0)
        self.events.append({"min": max(self.minute, 1), "type": "sub", "side": side, "out": out.id, "in": repl.id,
                            "reason": "manager"})
        return True

    # ---------------------------------------------------------------- engine
    def _substitute(self, team: TeamState, out: Player, minute: int, reason: str) -> None:
        idx = next((i for i, (_, p) in enumerate(team.lineup) if p.id == out.id), None)
        if idx is None:
            return
        slot = team.lineup[idx][0]
        self.minutes_played[out.id] = minute - self.starts.get(out.id, 0)
        if team.subs >= 5 or not team.bench:
            if reason == "injury":
                team.lineup.pop(idx)
            return
        repl = max(team.bench, key=lambda p: slot_skill(p, slot) * condition(p))
        team.bench.remove(repl)
        team.lineup[idx] = (slot, repl)
        team.subs += 1
        self.starts[repl.id] = minute
        self.minutes_played.setdefault(repl.id, 0)
        self.events.append({"min": minute, "type": "sub", "side": self.teams.index(team), "out": out.id,
                            "in": repl.id, "reason": reason})

    def run(self, to_minute: int = 90, auto_subs_for: tuple = (0, 1)) -> None:
        rng, teams, events = self.rng, self.teams, self.events
        h, a = teams
        for minute in range(self.minute + 1, to_minute + 1):
            sh, sa = h.strengths(), a.strengths()
            xg_h, poss_h = expected_goals(sh, sa, True)
            xg_a, _ = expected_goals(sa, sh, False)
            self.poss_sum += poss_h
            for side, team, xg in ((0, h, xg_h), (1, a, xg_a)):
                opp = teams[1 - side]
                if rng.random() < xg * 10.6 / 90:
                    team.shots += 1
                    shooter = weighted_pick(rng, team.lineup, {"FW": 6, "MF": 2.5, "DF": 0.6, "GK": 0})
                    if shooter is None:
                        continue
                    quality = min(0.85, rng.expovariate(1 / 0.108))
                    team.xg += quality
                    if rng.random() < quality:
                        team.on_target += 1
                        team.goals += 1
                        assist = None
                        if rng.random() < 0.75:
                            others = [(s, p) for s, p in team.lineup if p.id != shooter.id]
                            assist = weighted_pick(rng, others, {"MF": 5, "FW": 3, "DF": 1.5, "GK": 0.1})
                        self.goals_by[shooter.id] = self.goals_by.get(shooter.id, 0) + 1
                        if assist:
                            self.assists_by[assist.id] = self.assists_by.get(assist.id, 0) + 1
                        events.append({"min": minute, "type": "goal", "side": side, "player": shooter.id,
                                       "assist": assist.id if assist else None, "score": [h.goals, a.goals]})
                    else:
                        big = quality > 0.25
                        if rng.random() < 0.38 + quality * 0.5:
                            team.on_target += 1
                            if self.detailed and (big or rng.random() < 0.08):
                                gk = next((p for s, p in opp.lineup if s == "GK"), None)
                                events.append({"min": minute, "type": "save", "side": side, "player": shooter.id,
                                               "gk": gk.id if gk else None})
                        elif self.detailed and big:
                            events.append({"min": minute, "type": "miss", "side": side, "player": shooter.id})
                if rng.random() < 1.9 / 90:
                    p = weighted_pick(rng, team.lineup, {"DF": 4, "MF": 3, "FW": 1.5, "GK": 0.3})
                    if p:
                        self.yellows[p.id] = self.yellows.get(p.id, 0) + 1
                        if self.yellows[p.id] >= 2:
                            self.reds.append(p.id)
                            team.reds += 1
                            team.lineup = [(s, x) for s, x in team.lineup if x.id != p.id]
                            self.minutes_played[p.id] = minute - self.starts.get(p.id, 0)
                            events.append({"min": minute, "type": "red", "side": side, "player": p.id, "second": True})
                        else:
                            events.append({"min": minute, "type": "yellow", "side": side, "player": p.id})
                if rng.random() < 0.055 / 90:
                    p = weighted_pick(rng, team.lineup, {"DF": 4, "MF": 2, "FW": 1, "GK": 0.3})
                    if p:
                        self.reds.append(p.id)
                        team.reds += 1
                        team.lineup = [(s, x) for s, x in team.lineup if x.id != p.id]
                        self.minutes_played[p.id] = minute - self.starts.get(p.id, 0)
                        events.append({"min": minute, "type": "red", "side": side, "player": p.id, "second": False})
                physio = self.world.staff.get("physio", {}).get("level", 0) if team.club.id == self.world.club_id else 0
                if rng.random() < 0.13 / 90 * (1 - 0.1 * physio):
                    p = weighted_pick(rng, team.lineup, {"DF": 1, "MF": 1, "FW": 1, "GK": 0.3})
                    if p:
                        weeks = rng.choices([1, 2, 3, 5, 8], weights=[35, 30, 18, 12, 5])[0]
                        weeks = max(1, round(weeks * (1 - 0.15 * physio)))
                        self.injuries.append((p.id, weeks))
                        events.append({"min": minute, "type": "injury", "side": side, "player": p.id, "weeks": weeks})
                        self._substitute(team, p, minute, "injury")
            if minute in (60, 70, 80):
                for side, team in enumerate(teams):
                    if side not in auto_subs_for or team.subs >= 5 or not team.bench:
                        continue
                    tired = [p for s, p in team.lineup if s != "GK" and p.fitness < 80]
                    tired.sort(key=lambda p: p.fitness)
                    for p in tired[:2 if minute < 80 else 1]:
                        self._substitute(team, p, minute, "tactical")
            self.minute = minute

    def finish(self) -> dict:
        rng, teams = self.rng, self.teams
        h, a = teams
        home, away = self.home, self.away
        for t in teams:
            for _, p in t.lineup:
                self.minutes_played[p.id] = 90 - self.starts.get(p.id, 0)
        all_players = {p.id: p for c in (home, away) for p in self.world.squad(c.id)}
        for side, t in enumerate(teams):
            opp = teams[1 - side]
            for pid, mins in self.minutes_played.items():
                p = all_players.get(pid)
                if p is None or p.club_id != t.club.id:
                    continue
                r = 6.2 + rng.gauss(0, 0.45) + (t.goals - opp.goals) * 0.18
                r += self.goals_by.get(pid, 0) * 1.0 + self.assists_by.get(pid, 0) * 0.6
                if p.pos in ("GK", "DF"):
                    r += 0.6 if opp.goals == 0 else -0.22 * opp.goals
                if pid in self.reds:
                    r -= 1.5
                elif self.yellows.get(pid):
                    r -= 0.3
                r += (p.skill - 60) / 40
                if mins < 20:
                    r = 6.0 + (r - 6.0) * 0.4
                t.ratings[pid] = round(max(3.0, min(10.0, r)), 1)
        motm, best = None, -1.0
        for t in teams:
            for pid, r in t.ratings.items():
                if r > best:
                    best, motm = r, pid
        return {
            "home": home.id, "away": away.id, "hg": h.goals, "ag": a.goals,
            "events": sorted(self.events, key=lambda e: e["min"]),
            "possession": round(self.poss_sum / max(1, self.minute) * 100),
            "shots": [h.shots, a.shots], "on_target": [h.on_target, a.on_target],
            "xg": [round(h.xg, 2), round(a.xg, 2)],
            "minutes": self.minutes_played, "ratings": {**h.ratings, **a.ratings},
            "goals_by": self.goals_by, "assists_by": self.assists_by,
            "yellows": self.yellows, "reds": self.reds, "injuries": self.injuries, "motm": motm,
            "fatigue": {0: STYLE_MODS.get(home.style, STYLE_MODS["balanced"])[4],
                        1: STYLE_MODS.get(away.style, STYLE_MODS["balanced"])[4]},
            "lineups": [[p.id for _, p in t.lineup] for t in teams], "xi": self.xi,
        }


def simulate(world: World, home: Club, away: Club, rng: random.Random | None = None, detailed: bool = False) -> dict:
    sim = Sim(world, home, away, rng or random.Random(), detailed)
    sim.run(90)
    return sim.finish()


def predict(world: World, home: Club, away: Club) -> dict:
    """Pre-match odds from both XIs (Poisson on the engine's expected goals)."""
    import math
    sim = Sim(world, home, away, random.Random(0))
    sh, sa = (t.strengths() for t in sim.teams)
    lh = expected_goals(sh, sa, True)[0] * 1.14
    la = expected_goals(sa, sh, False)[0] * 1.14
    pois = lambda l, k: math.exp(-l) * l ** k / math.factorial(k)
    ph = [pois(lh, k) for k in range(11)]
    pa = [pois(la, k) for k in range(11)]
    w = sum(ph[i] * pa[j] for i in range(11) for j in range(11) if i > j)
    d = sum(ph[i] * pa[i] for i in range(11))
    l = max(0.0, 1 - w - d)
    tot = w + d + l
    w, d, l = (round(100 * x / tot) for x in (w, d, l))
    score = max(((i, j) for i in range(6) for j in range(6)), key=lambda t: ph[t[0]] * pa[t[1]])
    return {"home": w, "draw": 100 - w - l, "away": l, "xg": [round(lh, 2), round(la, 2)], "score": list(score)}


def apply_result(world: World, res: dict, rng: random.Random) -> None:
    """Persist match effects on players: stats, fitness, cards, injuries, morale."""
    home, away = world.clubs[res["home"]], world.clubs[res["away"]]
    for side, c in enumerate((home, away)):
        if c.id == world.club_id and res.get("xi"):
            world.last_xi = list(res["xi"][side])
    for pid, mins in res["minutes"].items():
        p = world.players.get(int(pid))
        if p is None:
            continue
        side = 0 if p.club_id == home.id else 1
        p.apps += 1
        p.career_apps += 1
        p.rating_sum += res["ratings"].get(pid, 6.0)
        drain = (mins / 90) * (14 + rng.uniform(0, 8) + res["fatigue"][side])
        if p.age >= 31:
            drain *= 1.15
        p.fitness = max(30, int(p.fitness - drain))
    for pid, g in res["goals_by"].items():
        p = world.players.get(int(pid))
        if p:
            p.goals += g
            p.career_goals += g
    for pid, a in res["assists_by"].items():
        p = world.players.get(int(pid))
        if p:
            p.assists += a
    for pid, n in res["yellows"].items():
        p = world.players.get(int(pid))
        if p and int(pid) not in res["reds"]:
            p.yellows += 1
            if p.yellows % 5 == 0:
                p.suspended = max(p.suspended, 1)
    for pid in res["reds"]:
        p = world.players.get(int(pid))
        if p:
            p.suspended = max(p.suspended, 1 if res["yellows"].get(pid, 0) >= 2 else rng.choice([1, 2, 3]))
    for pid, weeks in res["injuries"]:
        p = world.players.get(int(pid))
        if p:
            p.injured = max(p.injured, weeks)
    # morale
    for club, gf, ga in ((home, res["hg"], res["ag"]), (away, res["ag"], res["hg"])):
        delta = 4 if gf > ga else (-4 if gf < ga else 0)
        for p in world.squad(club.id):
            played = p.id in res["minutes"]
            d = delta + (1 if played else -1)
            p.morale = max(10, min(100, p.morale + d))
