"""Minute-by-minute match engine."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .models import FORMATIONS, Club, Player, World

STYLE_MODS = {
    #            att   mid   def   poss  fatigue
    "balanced": (1.00, 1.00, 1.00, 1.00, 0),
    "attacking": (1.07, 1.00, 0.94, 1.03, 2),
    "defensive": (0.92, 0.99, 1.07, 0.95, -2),
    "counter": (1.03, 0.97, 1.03, 0.90, 0),
    "pressing": (1.02, 1.06, 0.99, 1.05, 5),
}


def slot_skill(p: Player, slot: str) -> float:
    if p.pos == slot:
        return float(p.skill)
    if slot == "GK" or p.pos == "GK":
        return p.skill * 0.45
    return p.skill * 0.78


def condition(p: Player) -> float:
    return (0.72 + 0.28 * p.fitness / 100) * (0.94 + 0.12 * p.morale / 100)


def pick_lineup(world: World, club: Club) -> list[tuple[str, Player]]:
    d, m, f = FORMATIONS.get(club.formation, (4, 4, 2))
    pool = [p for p in world.squad(club.id) if p.available and not (club.is_user and p.resting)]
    if len([p for p in pool]) < 11:  # emergency: use resting players too
        pool = [p for p in world.squad(club.id) if p.available]
    lineup: list[tuple[str, Player]] = []
    used: set[int] = set()
    for slot, n in (("GK", 1), ("DF", d), ("MF", m), ("FW", f)):
        for _ in range(n):
            cands = [p for p in pool if p.id not in used]
            if not cands:
                break
            best = max(cands, key=lambda p: slot_skill(p, slot) * condition(p))
            used.add(best.id)
            lineup.append((slot, best))
    return lineup


def bench(world: World, club: Club, lineup) -> list[Player]:
    used = {p.id for _, p in lineup}
    pool = [p for p in world.squad(club.id) if p.available and p.id not in used]
    pool.sort(key=lambda p: p.skill * condition(p), reverse=True)
    return pool[:7]


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

    def line(self, slot: str) -> list[float]:
        return [slot_skill(p, s) * condition(p) for s, p in self.lineup if s == slot]

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
    items = [(p, weights.get(s, 1) * max(p.skill, 1)) for s, p in lineup]
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
    xg = 1.25 * (attack / defence) ** 3 * (0.55 + 0.9 * poss) * (1.12 if home else 0.93)
    return max(0.15, min(4.5, xg)), poss


def simulate(world: World, home: Club, away: Club, rng: random.Random | None = None, detailed: bool = False) -> dict:
    rng = rng or random.Random()
    teams = []
    for c in (home, away):
        lu = pick_lineup(world, c)
        teams.append(TeamState(club=c, lineup=lu, bench=bench(world, c, lu)))
    h, a = teams
    events: list[dict] = []
    yellows: dict[int, int] = {}
    poss_sum = 0.0
    minutes_played: dict[int, int] = {p.id: 0 for t in teams for _, p in t.lineup}
    starts = {p.id: 0 for t in teams for _, p in t.lineup}
    goals_by: dict[int, int] = {}
    assists_by: dict[int, int] = {}
    injuries: list[tuple[int, int]] = []
    reds: list[int] = []

    def substitute(team: TeamState, out: Player, minute: int, reason: str) -> None:
        idx = next((i for i, (_, p) in enumerate(team.lineup) if p.id == out.id), None)
        if idx is None:
            return
        slot = team.lineup[idx][0]
        minutes_played[out.id] = minute - starts.get(out.id, 0)
        if team.subs >= 5 or not team.bench:
            if reason == "injury":
                team.lineup.pop(idx)
            return
        repl = max(team.bench, key=lambda p: slot_skill(p, slot) * condition(p))
        team.bench.remove(repl)
        team.lineup[idx] = (slot, repl)
        team.subs += 1
        starts[repl.id] = minute
        minutes_played.setdefault(repl.id, 0)
        events.append({"min": minute, "type": "sub", "side": teams.index(team), "out": out.id, "in": repl.id,
                       "reason": reason})

    for minute in range(1, 91):
        sh, sa = h.strengths(), a.strengths()
        xg_h, poss_h = expected_goals(sh, sa, True)
        xg_a, _ = expected_goals(sa, sh, False)
        poss_sum += poss_h
        for side, team, xg in ((0, h, xg_h), (1, a, xg_a)):
            opp = teams[1 - side]
            # chances
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
                    goals_by[shooter.id] = goals_by.get(shooter.id, 0) + 1
                    if assist:
                        assists_by[assist.id] = assists_by.get(assist.id, 0) + 1
                    events.append({"min": minute, "type": "goal", "side": side, "player": shooter.id,
                                   "assist": assist.id if assist else None, "score": [h.goals, a.goals]})
                else:
                    big = quality > 0.25
                    if rng.random() < 0.38 + quality * 0.5:
                        team.on_target += 1
                        if detailed and (big or rng.random() < 0.08):
                            gk = next((p for s, p in opp.lineup if s == "GK"), None)
                            events.append({"min": minute, "type": "save", "side": side, "player": shooter.id,
                                           "gk": gk.id if gk else None})
                    elif detailed and big:
                        events.append({"min": minute, "type": "miss", "side": side, "player": shooter.id})
            # discipline
            if rng.random() < 1.9 / 90:
                p = weighted_pick(rng, team.lineup, {"DF": 4, "MF": 3, "FW": 1.5, "GK": 0.3})
                if p:
                    yellows[p.id] = yellows.get(p.id, 0) + 1
                    if yellows[p.id] >= 2:
                        reds.append(p.id)
                        team.reds += 1
                        team.lineup = [(s, x) for s, x in team.lineup if x.id != p.id]
                        minutes_played[p.id] = minute - starts.get(p.id, 0)
                        events.append({"min": minute, "type": "red", "side": side, "player": p.id, "second": True})
                    else:
                        events.append({"min": minute, "type": "yellow", "side": side, "player": p.id})
            if rng.random() < 0.055 / 90:
                p = weighted_pick(rng, team.lineup, {"DF": 4, "MF": 2, "FW": 1, "GK": 0.3})
                if p:
                    reds.append(p.id)
                    team.reds += 1
                    team.lineup = [(s, x) for s, x in team.lineup if x.id != p.id]
                    minutes_played[p.id] = minute - starts.get(p.id, 0)
                    events.append({"min": minute, "type": "red", "side": side, "player": p.id, "second": False})
            if rng.random() < 0.13 / 90:
                p = weighted_pick(rng, team.lineup, {"DF": 1, "MF": 1, "FW": 1, "GK": 0.3})
                if p:
                    weeks = rng.choices([1, 2, 3, 5, 8], weights=[35, 30, 18, 12, 5])[0]
                    injuries.append((p.id, weeks))
                    events.append({"min": minute, "type": "injury", "side": side, "player": p.id, "weeks": weeks})
                    substitute(team, p, minute, "injury")
        # tactical/fatigue subs
        if minute in (60, 70, 80):
            for team in teams:
                if team.subs >= 5 or not team.bench:
                    continue
                tired = [p for s, p in team.lineup if s != "GK" and p.fitness < 80]
                tired.sort(key=lambda p: p.fitness)
                for p in tired[:2 if minute < 80 else 1]:
                    substitute(team, p, minute, "tactical")

    for t in teams:
        for _, p in t.lineup:
            minutes_played[p.id] = 90 - starts.get(p.id, 0)

    # ratings
    all_players = {p.id: p for c in (home, away) for p in world.squad(c.id)}
    for side, t in enumerate(teams):
        opp = teams[1 - side]
        for pid, mins in minutes_played.items():
            p = all_players.get(pid)
            if p is None or p.club_id != t.club.id:
                continue
            r = 6.2 + rng.gauss(0, 0.45) + (t.goals - opp.goals) * 0.18
            r += goals_by.get(pid, 0) * 1.0 + assists_by.get(pid, 0) * 0.6
            if p.pos in ("GK", "DF"):
                r += 0.6 if opp.goals == 0 else -0.22 * opp.goals
            if pid in reds:
                r -= 1.5
            elif yellows.get(pid):
                r -= 0.3
            r += (p.skill - 60) / 40
            if mins < 20:
                r = 6.0 + (r - 6.0) * 0.4
            t.ratings[pid] = round(max(3.0, min(10.0, r)), 1)

    motm = None
    best = -1.0
    for t in teams:
        for pid, r in t.ratings.items():
            if r > best:
                best, motm = r, pid

    shots_on = [h.on_target, a.on_target]
    return {
        "home": home.id, "away": away.id, "hg": h.goals, "ag": a.goals,
        "events": sorted(events, key=lambda e: e["min"]),
        "possession": round(poss_sum / 90 * 100),
        "shots": [h.shots, a.shots], "on_target": shots_on,
        "xg": [round(h.xg, 2), round(a.xg, 2)],
        "minutes": minutes_played, "ratings": {**h.ratings, **a.ratings},
        "goals_by": goals_by, "assists_by": assists_by,
        "yellows": yellows, "reds": reds, "injuries": injuries, "motm": motm,
        "fatigue": {0: STYLE_MODS.get(home.style, STYLE_MODS["balanced"])[4],
                    1: STYLE_MODS.get(away.style, STYLE_MODS["balanced"])[4]},
        "lineups": [[p.id for _, p in t.lineup] for t in teams],
    }


def apply_result(world: World, res: dict, rng: random.Random) -> None:
    """Persist match effects on players: stats, fitness, cards, injuries, morale."""
    home, away = world.clubs[res["home"]], world.clubs[res["away"]]
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
