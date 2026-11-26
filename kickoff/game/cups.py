"""National cup and Champions League: draws, schedules, ties, league phase and knockouts.

Competitions live in world.cups as plain JSON-friendly dicts. A stage is played before the league
round given by stage["round"]; the user's own matches are returned to be shown live.
"""
from __future__ import annotations

import random

from .leagues import LEAGUES
from .lore import EURO, euro_for
from .match import apply_result, pick_lineup, simulate

CUP_NAMES = {"UA": "Кубок України", "EN": "Кубок Англії", "ES": "Кубок Короля", "DE": "Кубок Німеччини",
             "IT": "Кубок Італії", "FR": "Кубок Франції"}
KO_NAMES = {2: "Фінал", 4: "1/2 фіналу", 8: "1/4 фіналу", 16: "1/8 фіналу", 32: "1/16 фіналу", 64: "1/32 фіналу"}
UCL_SIZE = 24
UCL_MD = 6


def strength(w, club) -> float:
    lu = pick_lineup(w, club, auto=True)
    return sum(p.skill for _, p in lu) / max(1, len(lu)) + club.reputation / 100


def spread(n: int, start: int, total: int) -> list[int]:
    lo, hi = max(1, start), max(1, total - 1)
    if hi <= lo:
        return [lo] * n
    return [lo + round((k + 1) * (hi - lo) / (n + 1)) for k in range(n)]


# ---------------------------------------------------------------- setup
def setup(w, rng: random.Random, start_round: int = 0) -> None:
    total = w.rounds_total or 30
    w.cups = {}
    nation = LEAGUES[w.club.division]["nation"]
    ids = [c.id for c in w.clubs.values() if LEAGUES[c.division]["nation"] == nation]
    ids.sort(key=lambda i: -w.clubs[i].reputation)
    size = 2
    while size < len(ids):
        size *= 2
    stages, n = [], size
    while n >= 2:
        stages.append({"label": KO_NAMES.get(n, f"1/{n // 2} фіналу"), "type": "single", "ties": [], "done": False})
        n //= 2
    for st, r in zip(stages, spread(len(stages), start_round, total)):
        st["round"] = r
    cup = {"key": "cup", "name": CUP_NAMES.get(nation, "Кубок"), "icon": "🏆", "stages": stages, "alive": ids,
           "winner": None, "seen": -1, "out": []}
    draw_knockout(w, cup, 0, rng, byes=size - len(ids))
    w.cups["cup"] = cup

    teams = ucl_teams(w)
    md_rounds = spread(UCL_MD + 7, start_round, total)
    ucl_stages = [{"label": f"Загальний етап · тур {k + 1}", "type": "league", "ties": [], "done": False,
                   "round": md_rounds[k]} for k in range(UCL_MD)]
    for i, (label, typ) in enumerate([("1/8 фіналу · 1-й матч", "leg1"), ("1/8 фіналу · 2-й матч", "leg2"),
                                       ("1/4 фіналу · 1-й матч", "leg1"), ("1/4 фіналу · 2-й матч", "leg2"),
                                       ("1/2 фіналу · 1-й матч", "leg1"), ("1/2 фіналу · 2-й матч", "leg2"),
                                       ("Фінал", "single")]):
        ucl_stages.append({"label": label, "type": typ, "ties": [], "done": False, "round": md_rounds[UCL_MD + i]})
    order = list(teams)
    rng.shuffle(order)
    from .season import round_robin  # local import: season imports this module
    rr = round_robin(order, rng)
    for k in range(UCL_MD):
        ucl_stages[k]["ties"] = [{"a": h, "b": a, "legs": [], "winner": None} for h, a in rr[k]]
    w.cups["ucl"] = {"key": "ucl", "name": "Ліга чемпіонів", "icon": "⭐", "stages": ucl_stages, "alive": teams,
                     "teams": teams, "winner": None, "seen": UCL_MD - 1, "out": []}


def ucl_teams(w) -> list[int]:
    prev = [i for i in (w.euro_next or {}).get("UCL", []) if i in w.clubs]
    if len(prev) >= 16:
        teams = prev[:UCL_SIZE]
    else:
        teams, extra = [], []
        for lid in EURO:
            ranked = sorted(w.division_clubs(lid), key=lambda c: -strength(w, c))
            for i, c in enumerate(ranked):
                code = euro_for(lid, i + 1) or ""
                if code.startswith("UCL"):
                    teams.append(c.id)
                elif code.startswith("UEL"):
                    extra.append(c)
        extra.sort(key=lambda c: -strength(w, c))
        teams += [c.id for c in extra[:max(0, UCL_SIZE - len(teams))]]
    if len(teams) % 2:
        teams = teams[:-1]
    return teams


def qualify(w, tables: dict) -> None:
    """At season end: next season's Champions League clubs from the final tables (+ the holder)."""
    teams = []
    extra = []
    for lid in EURO:
        rows = tables.get(lid) or []
        for i, r in enumerate(rows):
            code = euro_for(lid, i + 1) or ""
            if code.startswith("UCL"):
                teams.append(r["club"])
            elif code.startswith("UEL"):
                extra.append(r["club"])
    holder = (w.cups.get("ucl") or {}).get("winner")
    if holder and holder not in teams:
        teams.insert(0, holder)
    teams += [c for c in extra if c not in teams][:max(0, UCL_SIZE - len(teams))]
    w.euro_next = {"UCL": teams[:UCL_SIZE]}


def ensure(w, rng: random.Random | None = None) -> None:
    """Old saves get competitions for the rest of the current season."""
    if not w.cups and w.round < (w.rounds_total or 0) - 1:
        setup(w, rng or random.Random(), start_round=w.round)


# ---------------------------------------------------------------- draws
def draw_knockout(w, comp: dict, idx: int, rng: random.Random, byes: int = 0, seeded: list | None = None) -> None:
    st = comp["stages"][idx]
    alive = sorted(comp["alive"], key=lambda i: -w.clubs[i].reputation)
    ties = []
    if seeded:  # [(top pot), (bottom pot)] -> each top club meets a random bottom club, top club hosts 2nd leg
        top, bottom = list(seeded[0]), list(seeded[1])
        rng.shuffle(bottom)
        for a, b in zip(top, bottom):
            ties.append({"a": b, "b": a, "legs": [], "winner": None})
    else:
        free = alive[byes:]
        rng.shuffle(free)
        for i in range(0, len(free) - 1, 2):
            ties.append({"a": free[i], "b": free[i + 1], "legs": [], "winner": None})
        for cid in alive[:byes]:
            ties.append({"a": cid, "b": None, "legs": [], "winner": cid})
    st["ties"] = ties
    st["drawn"] = True
    if idx + 1 < len(comp["stages"]) and comp["stages"][idx + 1]["type"] == "leg2":
        comp["stages"][idx + 1]["ties"] = [{"a": t["a"], "b": t["b"], "legs": [], "winner": None, "ref": n}
                                           for n, t in enumerate(ties)]


# ---------------------------------------------------------------- queries
def next_stage(comp: dict) -> int | None:
    for i, st in enumerate(comp["stages"]):
        if not st["done"]:
            return i
    return None


def due(w) -> list[str]:
    out = []
    for key, comp in (w.cups or {}).items():
        i = next_stage(comp)
        if i is not None and comp["stages"][i]["round"] <= w.round and comp["stages"][i]["ties"]:
            out.append(key)
    return sorted(out, key=lambda k: (w.cups[k]["stages"][next_stage(w.cups[k])]["round"], k != "cup"))


def user_tie(w, key: str) -> tuple[int, dict] | None:
    comp = w.cups[key]
    i = next_stage(comp)
    if i is None:
        return None
    for t in comp["stages"][i]["ties"]:
        if w.club_id in (t["a"], t["b"]) and t["b"] is not None:
            return i, t
    return None


def user_next(w) -> dict | None:
    """The user's next cup/European match if it comes before the next league round."""
    for key in due(w):
        ut = user_tie(w, key)
        if ut:
            i, t = ut
            comp = w.cups[key]
            st = comp["stages"][i]
            h, a = (t["b"], t["a"]) if st["type"] == "leg2" else (t["a"], t["b"])
            first = None
            if st["type"] == "leg2":
                ref = comp["stages"][i - 1]["ties"][t.get("ref", 0)]
                first = ref["legs"][0] if ref["legs"] else None
            return {"key": key, "stage": i, "home": h, "away": a, "first": first,
                    "name": comp["name"], "icon": comp["icon"], "label": st["label"]}
    return None


def pending_draw(w) -> dict | None:
    for key, comp in (w.cups or {}).items():
        i = next_stage(comp)
        if i is None or i <= comp.get("seen", -1):
            continue
        st = comp["stages"][i]
        if st["type"] in ("single", "leg1") and st.get("drawn") and w.club_id in comp["alive"]:
            return {"key": key, "stage": i}
    return None


def league_table(w, comp: dict) -> list[dict]:
    rows = {c: {"club": c, "p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "pts": 0} for c in comp.get("teams", [])}
    for st in comp["stages"]:
        if st["type"] != "league":
            continue
        for t in st["ties"]:
            for lg in t["legs"]:
                for cid, gf, ga in ((lg["h"], lg["hg"], lg["ag"]), (lg["a"], lg["ag"], lg["hg"])):
                    r = rows.get(cid)
                    if not r:
                        continue
                    r["p"] += 1
                    r["gf"] += gf
                    r["ga"] += ga
                    if gf > ga:
                        r["w"] += 1
                        r["pts"] += 3
                    elif gf == ga:
                        r["d"] += 1
                        r["pts"] += 1
                    else:
                        r["l"] += 1
    return sorted(rows.values(), key=lambda r: (-r["pts"], -(r["gf"] - r["ga"]), -r["gf"],
                                                -w.clubs[r["club"]].reputation))


# ---------------------------------------------------------------- play
PRIZE = {"cup": 150_000, "ucl": 2_000_000}


def _penalties(rng: random.Random) -> tuple[int, int]:
    a = rng.choice([3, 4, 4, 5, 5])
    b = a - 1 if rng.random() < .5 else a + 1
    if b > 5:
        a, b = 5, 4
    return (a, b) if rng.random() < .5 else (b, a)


def play_stage(w, key: str, rng: random.Random, user_res: dict | None = None) -> dict | None:
    comp = w.cups[key]
    i = next_stage(comp)
    st = comp["stages"][i]
    injected, user_res = user_res, None
    money = LEAGUES[w.club.division]["money"]
    for t in st["ties"]:
        if t["b"] is None:
            continue
        h, a = (t["b"], t["a"]) if st["type"] == "leg2" else (t["a"], t["b"])
        mine = w.club_id in (h, a)
        if injected and (injected["home"], injected["away"]) == (h, a):
            res = injected
        else:
            res = simulate(w, w.clubs[h], w.clubs[a], rng, detailed=mine)
        apply_result(w, res, rng)
        from .season import gate_income  # local import: season imports this module
        att, gate = gate_income(w, w.clubs[h], rng)
        res["attendance"] = att
        w.clubs[h].budget += gate
        if h == w.club_id:
            w.season_finances["income"] += gate
        leg = {"h": h, "a": a, "hg": res["hg"], "ag": res["ag"]}
        winner = None
        if st["type"] == "single":
            if res["hg"] != res["ag"]:
                winner = h if res["hg"] > res["ag"] else a
            else:
                ph, pa = _penalties(rng)
                leg["pens"] = [ph, pa]
                winner = h if ph > pa else a
        elif st["type"] == "leg2":
            ref = comp["stages"][i - 1]["ties"][t.get("ref", 0)]
            f = ref["legs"][0] if ref["legs"] else {"h": a, "a": h, "hg": 0, "ag": 0}
            agg = {h: res["hg"], a: res["ag"]}
            agg[f["h"]] = agg.get(f["h"], 0) + f["hg"]
            agg[f["a"]] = agg.get(f["a"], 0) + f["ag"]
            leg["agg"] = [agg[h], agg[a]]
            if agg[h] != agg[a]:
                winner = h if agg[h] > agg[a] else a
            else:
                ph, pa = _penalties(rng)
                leg["pens"] = [ph, pa]
                winner = h if ph > pa else a
        t["legs"].append(leg)
        t["winner"] = winner
        if mine:
            gf, ga = (res["hg"], res["ag"]) if h == w.club_id else (res["ag"], res["hg"])
            if gf > ga or winner == w.club_id:
                bonus = int(PRIZE[key] * (money if key == "cup" else 1))
                w.club.budget += bonus
                w.season_finances["income"] += bonus
            res["comp"] = {"key": key, "name": comp["name"], "icon": comp["icon"], "label": st["label"],
                           "agg": leg.get("agg"), "pens": leg.get("pens"),
                           "through": None if winner is None else winner == w.club_id}
            user_res = res
    st["done"] = True
    _advance(w, comp, i, rng)
    return user_res


def _advance(w, comp: dict, i: int, rng: random.Random) -> None:
    st = comp["stages"][i]
    nxt = i + 1 if i + 1 < len(comp["stages"]) else None
    if st["type"] == "league":
        if nxt is not None and comp["stages"][nxt]["type"] != "league":
            rows = league_table(w, comp)
            top = [r["club"] for r in rows[:16]]
            gone = [r["club"] for r in rows[16:]]
            comp["alive"] = top
            if w.club_id in gone:
                comp["out"].append(w.club_id)
                w.add_news(f"⭐ {comp['name']}: вибули на загальному етапі.")
            elif w.club_id in top:
                w.add_news(f"⭐ {comp['name']}: вийшли в 1/8 фіналу!")
            draw_knockout(w, comp, nxt, rng, seeded=[top[:8], top[8:]])
        return
    if st["type"] == "leg1":
        return
    winners = [t["winner"] for t in st["ties"] if t["winner"]]
    was_in = w.club_id in comp["alive"]
    comp["alive"] = winners
    if was_in and w.club_id not in winners:
        comp["out"].append(w.club_id)
        w.add_news(f"{comp['icon']} {comp['name']}: виліт на стадії «{st['label'].split(' · ')[0]}».")
    if len(winners) == 1:
        comp["winner"] = winners[0]
        champ = w.clubs[winners[0]]
        if champ.id == w.club_id:
            w.trophies.append(f"🏆 {comp['name']} (сезон {w.season})")
            w.confidence = min(100, w.confidence + 15)
            w.add_news(f"🏆 Ми виграли {comp['name']}!")
        else:
            w.add_news(f"{comp['icon']} {champ.name} виграв {comp['name']}.")
        return
    if nxt is not None:
        draw_knockout(w, comp, nxt, rng)
