"""aiohttp web server: Telegram Mini App static files + JSON API."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web

from ..game.leagues import LEAGUES
from ..game.match import TALKS, predict, _auto_fill, available_pool, chemistry, formation_slots, pick_lineup, prole
from ..game.roles import FORMATIONS as SLOTS, familiarity
from ..game.models import FORMATIONS, POS_NAME, SQUAD_MAX, STYLES, TRAINING
from ..game import cups as cupsmod
from ..game.lore import EURO_NAME, LORE, euro_for, generic_story
from ..game.roles import ROLES, line_of
from ..realdata import CREST_IMG, CREST_STATUS, CRESTS
from ..game.season import fair_ticket, next_fixture, position, season_over, sponsor_income, table, wage_bill
from ..game.transfers import asking_price, upgrade_cost, wage_demand
from ..meta import GEM_PACKS, MAX_SLOTS, PREMIUM, SHOP, SLOT_PRICE, today
from ..service import Service, locks
from ..game import transfers as tr
from ..game.names import flag

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


# ====================================================================== auth
def check_init_data(init_data: str, token: str, max_age: int = 7 * 86400) -> dict | None:
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received = pairs.pop("hash")
    except Exception:
        return None
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return None
    if time.time() - int(pairs.get("auth_date", "0")) > max_age:
        return None
    try:
        return json.loads(pairs.get("user", "{}"))
    except ValueError:
        return None


# ====================================================================== serializers
def season_label(season: int) -> str:
    y = 2025 + season
    return f"{y}/{str(y + 1)[-2:]}"


def club_json(w, c) -> dict:
    return {"id": c.id, "name": c.name, "city": c.city, "colors": c.colors, "crest": crest_url(c),
            "rep": c.reputation,
            "league": c.division, "leagueShort": LEAGUES[c.division]["short"], "country": c.country,
            "flag": LEAGUES[c.division]["flag"], "key": c.key}


def crest_url(c) -> str:
    if c.key in CREST_IMG:
        from urllib.parse import quote
        return "/crest/" + quote(c.key)
    return c.crest or CRESTS.get(c.key, "")


def player_json(w, p, xi: set | None = None) -> dict:
    return {"id": p.id, "name": p.name, "age": p.age, "pos": p.pos, "skill": p.skill, "pot": p.potential,
            "value": p.value(), "wage": p.wage, "fitness": p.fitness, "morale": p.morale,
            "contract": season_label(w.season + p.contract - 1), "contractYears": p.contract,
            "yellows": p.yellows, "injured": p.injured, "suspended": p.suspended, "listed": p.listed,
            "resting": p.resting, "youth": p.youth, "nation": p.nation, "flag": flag(p.nation), "number": p.number,
            "apps": p.apps, "goals": p.goals, "assists": p.assists, "rating": p.avg_rating, "real": p.real,
            "xi": bool(xi and p.id in xi), "club": p.club_id, "role": p.role, "loan": bool(p.loan)}


def team_rating(w, club) -> int:
    lu = pick_lineup(w, club, auto=True)
    return round(sum(p.skill for _, p in lu) / max(1, len(lu)))


def line_ratings(w, club) -> dict:
    lu = pick_lineup(w, club, auto=True)
    out = {}
    for line in ("GK", "DF", "MF", "FW"):
        xs = [p.skill for s, p in lu if line_of(s) == line]
        out[line] = round(sum(xs) / len(xs)) if xs else 0
    return out


def club_profile(w, c, rank: int, total: int) -> dict:
    squad = w.squad(c.id)
    stars = sorted(squad, key=lambda p: -p.skill)[:5]
    nick, story = LORE.get(c.key, (None, None))
    league = LEAGUES[c.division]
    euro = euro_for(c.division, rank)
    target = min(total, rank + 1)
    return {
        "lines": line_ratings(w, c), "avgAge": round(sum(p.age for p in squad) / max(1, len(squad)), 1),
        "value": sum(p.value() for p in squad), "wages": sum(p.wage for p in squad) * 52, "stadium": c.stadium,
        "size": len(squad), "foreign": sum(1 for p in squad if p.nation != league.get("nation")),
        "stars": [{"name": p.name, "role": p.role, "skill": p.skill, "flag": flag(p.nation), "age": p.age,
                   "number": p.number} for p in stars],
        "nick": nick, "story": story or generic_story(c.name, c.city, rank, total, league["short"]),
        "euro": {"code": euro, "name": EURO_NAME[euro][0], "icon": EURO_NAME[euro][1]} if euro else None,
        "rank": rank, "of": total, "target": target,
        "difficulty": 1 if rank <= 2 else 2 if rank <= total // 3 else 3 if rank <= total * 2 // 3 else 4 if rank < total - 2 else 5,
        "formation": c.formation,
    }


def career_card(w) -> dict:
    c = w.club
    rows = table(w, c.division)
    pos = [r["club"] for r in rows].index(c.id) + 1
    row = rows[pos - 1]
    return {"slot": w.slot, "club": club_json(w, c), "season": season_label(w.season), "position": pos,
            "of": len(rows), "points": row["pts"], "trophies": len([t for t in w.trophies if t.startswith("🏆")]),
            "fired": w.fired, "round": w.round, "rounds": w.rounds_total}


def profile_json(svc: Service, uid: int) -> dict:
    prof = svc.st.profile(uid)
    slots = svc.st.slots(uid)
    title, level, xp_in, xp_need = prof.rank
    out_slots = []
    for i in range(MAX_SLOTS):
        if i in slots:
            out_slots.append({"slot": i, "state": "career", "career": career_card(slots[i])})
        elif i < prof.slots_unlocked:
            out_slots.append({"slot": i, "state": "empty"})
        else:
            out_slots.append({"slot": i, "state": "locked", "price": SLOT_PRICE.get(i, 200)})
    active = prof.active_slot if prof.active_slot in slots else (min(slots) if slots else None)
    return {
        "user": {"name": prof.name, "username": prof.username, "photo": prof.photo_url},
        "coins": prof.coins, "xp": prof.xp, "rank": title, "level": level, "xpIn": xp_in, "xpNeed": xp_need,
        "daily": {"available": prof.daily_available(), "amount": prof.daily_amount(), "streak": prof.daily_streak},
        "tasks": prof.tasks(), "claimable": len(prof.claimable()),
        "slots": out_slots, "active": active,
        "shop": [{"id": k, **v} for k, v in SHOP.items()],
        "gems": prof.gems, "premium": [{"id": k, **v} for k, v in PREMIUM.items()], "packs": GEM_PACKS,
        "cosmetics": prof.cosmetics, "xpBoost": bool(prof.xp_boost_until and prof.xp_boost_until >= today()),
        "hall": [dict(zip(["manager", "club", "seasons", "titles", "promotions", "score"], r)) for r in svc.st.top(10)],
    }


def team_json(w) -> dict:
    c = w.club
    squad = w.squad(c.id)
    xi = {p.id for _, p in pick_lineup(w, c)}
    rows = table(w, c.division)
    my = next(r for r in rows if r["club"] == c.id)
    groups = []
    for pos in ("GK", "DF", "MF", "FW"):
        ps = sorted((p for p in squad if p.pos == pos), key=lambda p: -p.skill)
        groups.append({"pos": pos, "title": POS_NAME[pos], "players": [player_json(w, p, xi) for p in ps]})
    trophies = {}
    for t in w.trophies:
        k = "promo" if not t.startswith("🏆") else "ucl" if "Ліга чемпіонів" in t else "cup" if "Кубок" in t else "league"
        trophies[k] = trophies.get(k, 0) + 1
    return {
        "club": club_json(w, c), "season": season_label(w.season), "budget": c.budget,
        "stats": {"rating": team_rating(w, c), "wins": my["w"], "played": my["p"], "rounds": w.rounds_total,
                  "value": sum(p.value() for p in squad), "position": rows.index(my) + 1, "of": len(rows),
                  "points": my["pts"]},
        "trophies": trophies, "trophyList": w.trophies,
        "groups": groups, "count": len(squad), "max": SQUAD_MAX,
        "academyLevel": c.academy_level, "trainingLevel": c.training_level,
        "academyCost": upgrade_cost(w, "academy"), "trainingCost": upgrade_cost(w, "training"),
        "tactics": {"formation": c.formation, "style": c.style, "training": w.training,
                    "formations": list(FORMATIONS), "styles": STYLES, "trainings": TRAINING},
        "confidence": w.confidence, "target": w.board_target, "window": w.transfer_window_open(),
        "fired": w.fired, "seasonOver": season_over(w), "offers": len(w.offers),
        "jobs": len(w.records.get("jobs") or []),
    }


def short_name(n: str) -> str:
    parts = n.split()
    return parts[-1] if len(parts) > 1 else n


def lineup_json(w) -> dict:
    c = w.club
    lu = pick_lineup(w, c)
    layout = SLOTS.get(c.formation) or SLOTS["4-4-2"]
    by_slot = {}
    for i, (role, p) in enumerate(lu):
        by_slot[i] = p
    used = {p.id for _, p in lu}
    slots = []
    for i, (role, x, y) in enumerate(layout):
        p = by_slot.get(i)
        pj = None
        if p:
            fam = familiarity(prole(p), role)
            pj = {"id": p.id, "name": p.name, "short": short_name(p.name), "role": prole(p), "skill": p.skill,
                  "eff": round(p.skill * fam), "fam": round(fam, 2), "flag": flag(p.nation), "fitness": p.fitness,
                  "number": p.number}
        slots.append({"i": i, "role": role, "x": x, "y": y, "player": pj})
    pool = {p.id for p in available_pool(w, c)}
    others = []
    for p in sorted(w.squad(c.id), key=lambda p: -p.skill):
        if p.id in used:
            continue
        others.append({"id": p.id, "name": p.name, "short": short_name(p.name), "role": prole(p), "skill": p.skill,
                       "flag": flag(p.nation), "fitness": p.fitness, "ok": p.id in pool, "injured": p.injured,
                       "suspended": p.suspended, "resting": p.resting, "number": p.number})
    chem = chemistry(w, c, lu)
    custom = bool((w.lineups or {}).get(str(w.active_lineup)))
    captain = w.captain if w.captain in used else (max(lu, key=lambda t: t[1].skill)[1].id if lu else None)
    return {"formation": c.formation, "formations": list(SLOTS), "set": w.active_lineup,
            "sets": {str(k): bool((w.lineups or {}).get(str(k))) for k in (1, 2)}, "custom": custom,
            "slots": slots, "bench": others, "captain": captain, "chemistry": chem,
            "rating": round(sum(p.skill * familiarity(prole(p), r) for r, p in lu) / max(1, len(lu))),
            "style": c.style, "styles": STYLES, "roles": {k: v[1] for k, v in ROLES.items()},
            "fam": {a: {b: familiarity(a, b) for b in ROLES} for a in ROLES}}


def lineup_action(w, b: dict) -> tuple[bool, str | None]:
    c = w.club
    act = b.get("action")
    key = str(w.active_lineup)
    current = [None] * len(formation_slots(c))
    for i, (_, p) in enumerate(pick_lineup(w, c)):
        if i < len(current):
            current[i] = p.id
    if act == "assign":
        i, pid = int(b.get("slot", -1)), int(b.get("player", 0))
        if not 0 <= i < len(current):
            return False, "Немає такої позиції."
        pl = w.players.get(pid)
        if not pl or pl.club_id != c.id:
            return False, "Гравця немає в команді."
        if not pl.available:
            return False, "Гравець травмований або дискваліфікований."
        pl.resting = False
        if pid in current:  # swap two starters
            j = current.index(pid)
            current[i], current[j] = current[j], current[i]
        else:
            current[i] = pid
        w.lineups[key] = current
        return True, None
    if act == "auto":
        w.lineups.pop(key, None)
        return True, "Тренерський штаб зібрав найкращий склад."
    if act == "captain":
        pid = int(b.get("player", 0))
        if pid not in current:
            return False, "Капітан має бути в основі."
        w.captain = pid
        return True, "Новий капітан призначений."
    if act == "set":
        n = int(b.get("n", 1))
        if n not in (1, 2):
            return False, None
        w.active_lineup = n
        if b.get("copy") and not w.lineups.get(str(n)):
            w.lineups[str(n)] = current
        return True, None
    if act == "formation":
        f = b.get("formation")
        if f not in SLOTS:
            return False, "Невідома схема."
        players = [w.players[pid] for pid in current if pid in w.players]
        c.formation = f
        slots = formation_slots(c)
        chosen = _auto_fill(slots, [None] * len(slots), players)
        chosen = _auto_fill(slots, chosen, available_pool(w, c))
        if (w.lineups or {}).get(key):
            w.lineups[key] = [p.id if p else None for p in chosen]
        return True, None
    if act == "style" and b.get("style") in STYLES:
        c.style = b["style"]
        return True, None
    return False, "Невідома дія."


def dossier(w, opp, rows) -> dict:
    lines_me, lines_op = line_ratings(w, w.club), line_ratings(w, opp)
    squad = w.squad(opp.id)
    keys = sorted(squad, key=lambda p: -(p.skill + p.goals * 1.5))[:3]
    scorer = max(squad, key=lambda p: (p.goals, p.skill), default=None)
    row = next((r for r in rows if r["club"] == opp.id), None)
    h2h = [r for r in w.results if {r.home, r.away} == {w.club_id, opp.id}][-3:]
    tips = []
    if lines_op["FW"] >= lines_me["DF"] + 3:
        tips.append("Їхня атака сильніша за наш захист. Оборонний стиль або 5 захисників допоможуть.")
    if lines_me["FW"] >= lines_op["DF"] + 3:
        tips.append("Їхній захист вразливий. Атакувальний стиль може дати багато моментів.")
    if lines_op["MF"] >= lines_me["MF"] + 3:
        tips.append("Вони сильніші в центрі поля. Пресинг або контратаки нейтралізують перевагу.")
    if not tips:
        tips.append("Сили приблизно рівні. Вирішить форма і зіграність.")
    injured = sum(1 for p in squad if not p.available)
    return {
        "formation": opp.formation, "style": opp.style, "lines": lines_op, "mine": lines_me,
        "keys": [{"name": p.name, "role": p.role, "skill": p.skill, "flag": flag(p.nation), "goals": p.goals} for p in keys],
        "scorer": {"name": scorer.name, "goals": scorer.goals} if scorer and scorer.goals else None,
        "gf": row["gf"] if row else 0, "ga": row["ga"] if row else 0, "played": row["p"] if row else 0,
        "h2h": [{"home": w.clubs[r.home].name, "away": w.clubs[r.away].name, "hg": r.hg, "ag": r.ag} for r in h2h],
        "tips": tips, "missing": injured,
    }


def tie_json(w, t: dict) -> dict:
    c = lambda i: club_json(w, w.clubs[i]) if i is not None else None
    return {"a": c(t["a"]), "b": c(t["b"]), "legs": t["legs"], "winner": t.get("winner"),
            "mine": w.club_id in (t["a"], t["b"])}


def draw_json(w) -> dict | None:
    d = cupsmod.pending_draw(w)
    if not d:
        return None
    comp = w.cups[d["key"]]
    st = comp["stages"][d["stage"]]
    ties = [tie_json(w, t) for t in st["ties"]]
    ties.sort(key=lambda t: (t["b"] is None, not t["mine"]))
    return {"key": d["key"], "name": comp["name"], "icon": comp["icon"], "label": st["label"].split(" · ")[0],
            "ties": ties}


def calendar_json(w) -> dict:
    from ..game.schedule import calendar
    comps = {k: {"key": k, "name": c["name"], "icon": c["icon"]} for k, c in (w.cups or {}).items()}
    comps["league"] = {"key": "league", "name": LEAGUES[w.club.division]["short"], "icon": "📊"}
    out = []
    for e in calendar(w):
        d = {**e, "comp": comps.get(e["comp"], comps["league"])}
        d["home"] = club_json(w, w.clubs[e["home"]]) if e["home"] else None
        d["away"] = club_json(w, w.clubs[e["away"]]) if e["away"] else None
        if e["played"]:
            home = e["home"] == w.club_id
            gf, ga = (e["hg"], e["ag"]) if home else (e["ag"], e["hg"])
            res = "W" if gf > ga else "L" if gf < ga else "D"
            if res == "D" and e.get("pens"):
                ph, pa = e["pens"]
                res = "W" if (ph > pa) == home else "L"
            d["res"] = res
        d["isHome"] = e["home"] == w.club_id
        out.append(d)
    pl = [e for e in out if e.get("res")]
    return {"items": out, "played": len(pl), "total": len([e for e in out if not e.get("tbd")]),
            "w": sum(e["res"] == "W" for e in pl), "d": sum(e["res"] == "D" for e in pl),
            "l": sum(e["res"] == "L" for e in pl), "season": season_label(w.season)}


def totw_json(w) -> dict | None:
    t = w.totw
    if not t or t.get("season") != w.season:
        return None
    xi = []
    for x in t["xi"]:
        p = w.players.get(x["pid"])
        if not p:
            continue
        c = w.clubs.get(x["club"])
        xi.append({"id": p.id, "name": p.name, "pos": x["pos"], "rating": x["rating"], "skill": p.skill,
                   "flag": flag(p.nation), "club": club_json(w, c) if c else None, "mine": x["club"] == w.club_id,
                   "star": p.id == t.get("star")})
    top = sorted(((n, c) for n, c in w.records.get("totw", {}).items()), key=lambda kv: -kv[1])[:5]
    return {"round": t["round"], "xi": xi, "leaders": [{"name": n, "n": c} for n, c in top]}


def jobs_json(w) -> dict:
    from ..game import career
    from ..game.season import table as tbl
    items = []
    for j in w.records.get("jobs") or []:
        c = w.clubs.get(j["club"])
        if not c:
            continue
        rows = tbl(w, c.division)
        pos = next((i + 1 for i, r in enumerate(rows) if r["club"] == c.id), None)
        squad = w.squad(c.id)
        best = sorted(squad, key=lambda p: -p.skill)[:3]
        items.append({"club": club_json(w, c), "kind": j["kind"], "pitch": j["pitch"], "target": j["target"],
                      "budget": c.budget, "rating": team_rating(w, c), "pos": pos if w.round else None,
                      "league": LEAGUES[c.division]["short"], "leagueFlag": LEAGUES[c.division]["flag"],
                      "stars": [{"name": p.name, "skill": p.skill, "pos": p.pos} for p in best],
                      "left": (j.get("until", w.round) - w.round + 1) if j["kind"] == "approach" else None})
    log = [{"season": season_label(x["season"]), "from": w.clubs[x["from"]].name, "to": w.clubs[x["to"]].name}
           for x in w.records.get("career", []) if x["from"] in w.clubs and x["to"] in w.clubs]
    return {"items": items, "fired": w.fired, "rep": career.rep(w), "repLog": w.records.get("mrep_log", [])[:6],
            "career": log, "current": club_json(w, w.club), "myRating": team_rating(w, w.club)}


def loans_json(w) -> dict:
    from ..game import loans as ln

    def row(p, other):
        return {**player_json(w, p), "other": club_json(w, w.clubs[other]) if other in w.clubs else None}
    return {"out": [row(p, p.club_id) for p in ln.loaned_out(w)],
            "in": [row(p, p.loan) for p in ln.loaned_in(w)], "window": w.transfer_window_open()}


def cups_json(w) -> dict:
    out = []
    for key, comp in (w.cups or {}).items():
        stages = [{"label": st["label"], "type": st["type"], "done": st["done"], "round": st["round"],
                   "ties": [tie_json(w, t) for t in st["ties"]] if st["type"] != "league" else []}
                  for st in comp["stages"]]
        item = {"key": key, "name": comp["name"], "icon": comp["icon"], "stages": stages,
                "winner": club_json(w, w.clubs[comp["winner"]]) if comp.get("winner") else None,
                "in": w.club_id in (comp.get("teams") or comp["alive"]) or w.club_id in comp.get("out", []),
                "alive": w.club_id in comp["alive"]}
        if key == "ucl":
            item["table"] = [{"pos": i + 1, "club": club_json(w, w.clubs[r["club"]]), **{k: r[k] for k in ("p", "w", "d", "l", "gf", "ga", "pts")},
                              "me": r["club"] == w.club_id} for i, r in enumerate(cupsmod.league_table(w, comp))]
            item["played"] = sum(1 for st in comp["stages"] if st["type"] == "league" and st["done"])
        out.append(item)
    return {"comps": out}


def match_preview(w) -> dict:
    cupsmod.ensure(w)
    ev = cupsmod.user_next(w)
    nf = (ev["home"], ev["away"]) if ev else next_fixture(w)
    if not nf:
        return {"seasonOver": True, **life_json(w)}
    h, a = nf
    rows = table(w, w.club.division)
    pos = {r["club"]: i + 1 for i, r in enumerate(rows)}
    form = {r["club"]: r["form"][-5:] for r in rows}
    lu = pick_lineup(w, w.club)
    unavailable = [player_json(w, p) for p in w.squad(w.club_id) if not p.available]
    last = None
    if w.last_match:
        last = {"home": club_json(w, w.clubs[w.last_match["home"]]), "away": club_json(w, w.clubs[w.last_match["away"]]),
                "hg": w.last_match["hg"], "ag": w.last_match["ag"]}
    return {
        "round": w.round + 1, "rounds": w.rounds_total,
        "home": {**club_json(w, w.clubs[h]), "pos": pos.get(h), "form": form.get(h, []), "rating": team_rating(w, w.clubs[h])},
        "away": {**club_json(w, w.clubs[a]), "pos": pos.get(a), "form": form.get(a, []), "rating": team_rating(w, w.clubs[a])},
        "isHome": h == w.club_id, "formation": w.club.formation, "style": w.club.style, "styles": STYLES,
        "lineup": [{"slot": s, **player_json(w, p)} for s, p in lu], "unavailable": unavailable, "last": last,
        "xi": {k: v for k, v in lineup_json(w).items() if k in ("slots", "captain", "chemistry", "rating")},
        "dossier": dossier(w, w.clubs[a if h == w.club_id else h], rows),
        "comp": ({k: ev[k] for k in ("key", "name", "icon", "label")} |
                 ({"first": {"home": w.clubs[ev["first"]["h"]].name, "away": w.clubs[ev["first"]["a"]].name,
                             "hg": ev["first"]["hg"], "ag": ev["first"]["ag"]}} if ev.get("first") else {})) if ev else None,
        "draw": (lambda d: d if d and ev and d["key"] == ev["key"] else None)(draw_json(w)),
        "seasonOver": False, "predict": predict(w, w.clubs[h], w.clubs[a]), "pending": bool(w.pending),
        **life_json(w),
    }


def named_events(w, evs: list) -> list:
    def name(pid):
        p = w.players.get(int(pid)) if pid is not None else None
        return p.name if p else ""
    events = []
    for e in evs:
        e2 = dict(e)
        for k in ("player", "assist", "out", "in", "gk"):
            if e.get(k) is not None:
                e2[k + "Name"] = name(e[k])
        events.append(e2)
    return events


TALK_INFO = {"fire": ("🔥", "Розірвати їх!", "Шалена мотивація. Найкраще, коли програєш."),
             "calm": ("🧘", "Спокій і контроль", "Тримати результат. Добре при перевазі."),
             "praise": ("👏", "Похвалити", "Вселяє впевненість, якщо гра йде."),
             "blame": ("😤", "Рознос у роздягальні", "Ризиковано: або встряхне, або зламає.")}


def pitch_json(w, home, away, xi: list, events: list) -> dict:
    """Both starting XIs with formation coordinates for the live 2D match view."""
    sides = []
    for side, c in enumerate((home, away)):
        coords = SLOTS.get(c.formation) or SLOTS["4-4-2"]
        ps = []
        for i, pid in enumerate(xi[side] if side < len(xi) else []):
            p = w.players.get(int(pid))
            if not p:
                continue
            role, x, y = coords[i] if i < len(coords) else ("CM", 50, 50)
            ps.append({"id": p.id, "name": p.name, "short": p.name.split()[-1], "skill": p.skill, "role": role,
                       "x": x, "y": y, "gk": role == "GK"})
        sides.append(ps)
    extra = {}
    for e in events:
        if e.get("type") == "sub" and e.get("in") in w.players:
            p = w.players[e["in"]]
            extra[str(p.id)] = {"id": p.id, "name": p.name, "short": p.name.split()[-1], "skill": p.skill}
    everyone = [x for ps in sides for x in ps] + list(extra.values())
    count = {}
    for x in everyone:
        count[x["short"]] = count.get(x["short"], 0) + 1
    for x in everyone:
        if count[x["short"]] > 1 and len(x["name"].split()) > 1:
            x["short"] = f"{x['name'][0]}. {x['short']}"
    return {"sides": sides, "extra": extra, "colors": [home.colors, away.colors]}


def halftime_json(w, sim) -> dict:
    side = 0 if sim.home.id == w.club_id else 1
    t = sim.teams[side]
    pj = lambda s, p: {"slot": s, "id": p.id, "name": p.name, "role": p.role, "skill": p.skill,
                       "fitness": round(p.fitness)}
    poss = round(100 * sim.poss_sum / max(1, sim.minute)) if sim.minute else 50
    return {"half": True, "minute": sim.minute, "home": club_json(w, sim.home), "away": club_json(w, sim.away),
            "hg": sim.teams[0].goals, "ag": sim.teams[1].goals, "isHome": side == 0,
            "events": named_events(w, sim.events),
            "comp": (lambda ev: {k: ev[k] for k in ("key", "name", "icon", "label")} if ev else None)(cupsmod.user_next(w)),
            "shots": [sim.teams[0].shots, sim.teams[1].shots], "possession": [poss, 100 - poss],
            "xg": [round(sim.teams[0].xg, 2), round(sim.teams[1].xg, 2)],
            "lineup": [pj(s, p) for s, p in t.lineup], "bench": [pj(p.role, p) for p in t.bench],
            "subsLeft": 5 - t.subs, "style": w.club.style, "styles": STYLES,
            "pitch": pitch_json(w, sim.home, sim.away, sim.xi, sim.events),
            "talks": [{"id": k, "icon": v[0], "name": v[1], "hint": v[2]} for k, v in TALK_INFO.items()]}


def life_json(w) -> dict:
    return {"press": w.press or None, "dilemmas": w.dilemmas, "jobs": len(w.records.get("jobs") or []),
            "fired": w.fired}


def match_result_json(w, res: dict) -> dict:
    events = named_events(w, res["events"])
    ratings = []
    for pid, r in res["ratings"].items():
        p = w.players.get(int(pid))
        if p and p.club_id == w.club_id:
            ratings.append({"name": p.name, "pos": p.pos, "role": p.role, "rating": r, "goals": res["goals_by"].get(pid, 0)})
    ratings.sort(key=lambda x: -x["rating"])
    motm = w.players.get(int(res["motm"])) if res.get("motm") is not None else None
    return {"home": club_json(w, w.clubs[res["home"]]), "away": club_json(w, w.clubs[res["away"]]),
            "hg": res["hg"], "ag": res["ag"], "events": events, "possession": res["possession"],
            "shots": res["shots"], "onTarget": res["on_target"], "xg": res["xg"],
            "attendance": res.get("attendance", 0), "ratings": ratings,
            "motm": {"name": motm.name, "rating": res["ratings"].get(res["motm"])} if motm else None,
            "xp": res.get("xp", 0), "coins": res.get("coins", 0), "fired": w.fired, "seasonOver": season_over(w), "isHome": res["home"] == w.club_id,
            "comp": res.get("comp"), "records": res.get("records") or [], **life_json(w),
            "pitch": pitch_json(w, w.clubs[res["home"]], w.clubs[res["away"]], res.get("xi") or [[], []], res["events"])}


def records_json(w) -> dict:
    r = w.records
    top = lambda m: [{"name": k, "n": v} for k, v in sorted((m or {}).items(), key=lambda kv: -kv[1])[:5]]
    return {"club": club_json(w, w.club), "matches": r.get("matches", 0), "wins": r.get("wins", 0),
            "draws": r.get("draws", 0), "losses": r.get("losses", 0), "gf": r.get("gf", 0), "ga": r.get("ga", 0),
            "bigWin": r.get("big_win"), "bigLoss": r.get("big_loss"), "streak": r.get("streak", 0),
            "bestStreak": r.get("best_streak", 0), "scorers": top(r.get("scorers")), "apps": top(r.get("apps")),
            "awards": w.awards, "trophies": w.trophies, "history": w.history[-10:]}


def staff_json(w) -> dict:
    from ..game import staff as stf
    cands = stf.candidates(w)
    roles = []
    for d in stf.describe(w):
        cur = d["member"]["level"] if d["member"] else 0
        roles.append({**d, "candidates": [{**c, "flag": flag(c["nation"]), "fee": stf.hire_fee(w, c["level"]),
                                           "wage": stf.wage(w, c["level"]), "better": c["level"] > cur}
                                          for c in cands.get(d["role"], [])]})
    return {"roles": roles, "budget": w.club.budget, "wages": stf.staff_wages(w),
            "scout": [{**player_json(w, p), "clubInfo": club_json(w, w.clubs[p.club_id]) if p.club_id else None,
                       "price": asking_price(w, p.id) if p.club_id else 0} for p in stf.scout_picks(w)]}


def friends_json(svc, uid: int) -> dict:
    rows = []
    for f in svc.friends(uid):
        w = f.pop("world")
        rows.append({**f, "club": club_json(w, f["club"]), "league": LEAGUES[f["club"].division]["short"]})
    me = svc.st.profile(uid)
    return {"rows": rows, "weekly": me.weekly_list()}


def table_json(w, league: int) -> dict:
    rows = table(w, league)
    out = []
    for i, r in enumerate(rows, 1):
        c = w.clubs[r["club"]]
        out.append({"pos": i, "club": club_json(w, c), "p": r["p"], "w": r["w"], "d": r["d"], "l": r["l"],
                    "gf": r["gf"], "ga": r["ga"], "pts": r["pts"], "form": r["form"][-5:], "me": c.id == w.club_id})
    scorers = sorted((p for p in w.players.values() if p.club_id and w.clubs[p.club_id].division == league and p.goals),
                     key=lambda p: (p.goals, p.assists), reverse=True)[:10]
    zones = {"down": 2 if league == 1 else 0, "up": 2 if league == 2 else 0}
    return {"league": league, "leagues": [{"id": k, "short": v["short"], "flag": v["flag"]} for k, v in LEAGUES.items()],
            "name": LEAGUES[league]["name"], "rows": out, "zones": zones,
            "scorers": [{"name": p.name, "club": w.clubs[p.club_id].name, "goals": p.goals, "assists": p.assists,
                         "flag": flag(p.nation)} for p in scorers]}


def market_json(w, f: str, page: int, q: str) -> dict:
    others = [p for p in w.players.values() if p.club_id != w.club_id]
    if q:
        ql = q.lower()
        others = [p for p in others if ql in p.name.lower() or (p.club_id and ql in w.clubs[p.club_id].name.lower())]
    if f == "FA":
        ps = [p for p in others if p.club_id is None]
    elif f == "YT":
        ps = [p for p in others if p.age <= 21 and p.potential >= 72]
    elif f in ("GK", "DF", "MF", "FW"):
        ps = [p for p in others if p.pos == f]
    else:
        ps = others
    ps.sort(key=(lambda p: (-p.potential, -p.skill)) if f == "YT" else (lambda p: (-p.skill, -p.potential)))
    per = 20
    chunk = ps[page * per:(page + 1) * per]
    items = []
    for p in chunk:
        d = player_json(w, p)
        d["price"] = asking_price(w, p.id) if p.club_id else 0
        d["clubInfo"] = club_json(w, w.clubs[p.club_id]) if p.club_id else None
        items.append(d)
    offers = []
    for o in w.offers:
        p = w.players.get(o.player_id)
        if p:
            offers.append({"id": o.id, "fee": o.fee, "player": player_json(w, p), "club": club_json(w, w.clubs[o.club_id]),
                           "final": o.kind == "final", "ask": p.ask})
    pitches = []
    for x in w.pitches or []:
        p = w.players.get(x["pid"])
        if p and p.club_id not in (None, w.club_id):
            pitches.append({"id": x["id"], "fee": x["fee"], "note": x["note"], "until": x["until"] - w.round + 1,
                            "player": player_json(w, p), "club": club_json(w, w.clubs[p.club_id]),
                            "price": asking_price(w, p.id)})
    return {"items": items, "page": page, "pages": max(1, (len(ps) + per - 1) // per), "budget": w.club.budget,
            "window": w.transfer_window_open(), "offers": offers, "pitches": pitches,
            "listed": [{**player_json(w, p), "ask": p.ask} for p in w.squad(w.club_id) if p.listed], "count": len(w.squad(w.club_id)), "max": SQUAD_MAX}


def player_detail(w, pid: int) -> dict:
    p = w.players[pid]
    d = player_json(w, p)
    d["mine"] = p.club_id == w.club_id
    d["clubInfo"] = club_json(w, w.clubs[p.club_id]) if p.club_id else None
    if not d["mine"]:
        d["price"] = asking_price(w, pid) if p.club_id else 0
        d["wageDemand"] = wage_demand(w, pid)
        d["signBonus"] = wage_demand(w, pid) * 4 if p.club_id is None else 0
    d["careerGoals"], d["careerApps"] = p.career_goals, p.career_apps
    neg = (w.negotiations or {}).get(str(pid))
    d["negotiation"] = {"status": "counter", "counter": neg["counter"], "left": 3 - neg["n"]} if neg and neg.get("counter") else None
    d["window"] = w.transfer_window_open()
    if not d["mine"] and p.club_id:
        d["willJoin"], d["joinWhy"] = tr.will_join(w, pid)
    d["ask"] = p.ask
    from ..game import loans as ln
    if p.loan:
        d["loanFrom"] = club_json(w, w.clubs[p.loan]) if p.loan in w.clubs else None
    if not d["mine"] and p.club_id and not p.loan:
        d["loanFee"] = ln.loan_fee(p)
        d["canLoan"], d["loanWhy"] = ln.can_loan_in(w, pid)
    if d["mine"]:
        d["canLoanOut"] = not p.loan and d["window"]
        d["trainCost"] = tr.training_cost(p)
        d["canTrain"] = p.trained != w.season * 1000 + w.round and p.skill < min(99, p.potential)
    return d


def club_tab_json(w) -> dict:
    c = w.club
    f = w.season_finances
    return {"club": club_json(w, c), "budget": c.budget, "wages": wage_bill(w, c.id), "sponsor": sponsor_income(c),
            "stadium": c.stadium, "ticket": c.ticket_price, "fairTicket": fair_ticket(c), "finances": f,
            "training": c.training_level, "academy": c.academy_level, "reputation": c.reputation,
            "upgrades": {k: upgrade_cost(w, k) for k in ("stadium", "training", "academy")},
            "history": [{**h, "clubName": w.clubs[h["club"]].name, "league": LEAGUES[h["division"]]["short"],
                         "season": season_label(h["season"])} for h in w.history],
            "trophies": w.trophies, "news": w.news[:20], "confidence": w.confidence, "target": w.board_target,
            "manager": w.manager}


def finance_json(w) -> dict:
    from ..game import finance as fn, sponsors as sp
    c = w.club
    if not w.sponsor and not w.sponsor_offers:
        sp.make_offers(w)
    inc, exp = fn.totals(w)
    wages = wage_bill(w, c.id)
    left = max(0, w.rounds_total - w.round)
    pending = sum(a for a, paid in zip(w.sponsor.get("parts", []), w.sponsor.get("paid", [])) if not paid) \
        if w.sponsor and w.sponsor.get("left", 0) > 0 else 0
    weekly = sponsor_income(c) - wages
    forecast = c.budget + weekly * left + pending
    status = "good" if forecast > wages * 10 and weekly >= 0 else "tight" if forecast > 0 else "critical"
    cats = lambda d: [{"id": k, "icon": v[0], "name": v[1], "amount": w.fin.get(k, 0)} for k, v in d.items()
                      if w.fin.get(k, 0)]
    squad = sorted(w.squad(c.id), key=lambda p: -p.wage)
    spon = None
    if w.sponsor:
        spon = {**w.sponsor, "kindName": sp.KINDS[w.sponsor["kind"]][0]}
    return {"club": club_json(w, c), "season": season_label(w.season), "budget": c.budget, "income": inc,
            "expense": exp, "incomeCats": sorted(cats(fn.INCOME), key=lambda x: -x["amount"]),
            "expenseCats": sorted(cats(fn.EXPENSE), key=lambda x: -x["amount"]),
            "ledger": [{**e, "season": season_label(e["season"])} for e in w.ledger[:20]],
            "wagesWeekly": wages, "wagesSeason": wages * w.rounds_total, "commercialWeekly": sponsor_income(c),
            "staffWages": sum(stf_w(w)), "roundsLeft": left, "forecast": forecast, "status": status,
            "pendingSponsor": pending, "weekly": weekly,
            "earners": [{"id": p.id, "name": p.name, "role": p.role, "wage": p.wage, "skill": p.skill,
                         "contract": season_label(w.season + p.contract - 1)} for p in squad[:10]],
            "squadCount": len(squad),
            "history": [{"season": season_label(h["season"]),
                         "income": sum(v for k, v in h.items() if k in fn.INCOME),
                         "expense": sum(v for k, v in h.items() if k in fn.EXPENSE)} for h in w.fin_history],
            "sponsor": spon, "offers": [{**o, "kindName": sp.KINDS[o["kind"]][0], "kindHint": sp.KINDS[o["kind"]][1]}
                                        for o in w.sponsor_offers],
            "canChange": sp.can_change(w), "parts": list(sp.PARTS)}


def stf_w(w):
    from ..game.staff import staff_wages
    return [staff_wages(w)]


# ====================================================================== app
def create_app(svc: Service, token: str) -> web.Application:
    dev = os.getenv("DEV_AUTH") == "1"

    @web.middleware
    async def auth_mw(request, handler):
        if not request.path.startswith("/api/"):
            return await handler(request)
        user = None
        init = request.headers.get("X-Init-Data", "")
        if init and token:
            user = check_init_data(init, token)
        if user is None and dev:
            user = {"id": int(request.headers.get("X-Dev-User", "1")), "first_name": "Ілля", "username": "dev"}
        if not user or "id" not in user:
            return web.json_response({"error": "Відкрий гру через Telegram."}, status=401)
        request["user"] = user
        uid = int(user["id"])
        request["uid"] = uid
        async with locks[uid]:
            try:
                return await handler(request)
            except web.HTTPException:
                raise
            except Exception:
                log.exception("API error %s", request.path)
                return web.json_response({"error": "Помилка сервера, спробуй ще раз."}, status=500)

    app = web.Application(middlewares=[auth_mw])
    r = app.router

    async def body(request) -> dict:
        try:
            return await request.json()
        except Exception:
            return {}

    def ok(data=None, msg: str | None = None):
        out = {"ok": True}
        if msg:
            out["message"] = msg
        if data is not None:
            out["data"] = data
        return web.json_response(out)

    def fail(msg: str, status: int = 400):
        return web.json_response({"ok": False, "error": msg}, status=status)

    def sync_user(request):
        prof = svc.st.profile(request["uid"])
        u = request["user"]
        name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or prof.name
        changed = (prof.name, prof.username, prof.photo_url) != (name, u.get("username", ""), u.get("photo_url", prof.photo_url))
        prof.name, prof.username = name, u.get("username", "")
        if u.get("photo_url"):
            prof.photo_url = u["photo_url"]
        if changed:
            svc.st.save_profile(prof)
        return prof

    def world(request):
        prof = svc.st.profile(request["uid"])
        return svc.st.load(request["uid"], prof.active_slot), prof

    # ---------------- profile / meta
    async def get_profile(request):
        sync_user(request)
        return ok(profile_json(svc, request["uid"]))

    async def claim_daily(request):
        prof = svc.st.profile(request["uid"])
        good, msg, _ = prof.claim_daily()
        svc.st.save_profile(prof)
        return ok(profile_json(svc, request["uid"]), msg) if good else fail(msg)

    async def claim_task(request):
        prof = svc.st.profile(request["uid"])
        good, msg, _ = prof.claim_task((await body(request)).get("id", ""))
        svc.st.save_profile(prof)
        return ok(profile_json(svc, request["uid"]), msg) if good else fail(msg)

    async def unlock_slot(request):
        prof = svc.st.profile(request["uid"])
        good, msg = prof.unlock_slot()
        svc.st.save_profile(prof)
        return ok(profile_json(svc, request["uid"]), msg) if good else fail(msg)

    async def shop_buy(request):
        w, prof = world(request)
        b = await body(request)
        if b.get("premium"):
            good, msg = svc.buy_premium(w, prof, b.get("item", ""))
        else:
            good, msg = svc.buy_item(w, prof, b.get("item", ""))
        if good:
            svc.st.save(w)
            svc.st.save_profile(prof)
            return ok(profile_json(svc, request["uid"]), msg)
        return fail(msg)

    # ---------------- careers
    async def career_draft(request):
        slot = int((await body(request)).get("slot", 0))
        prof = sync_user(request)
        if slot >= prof.slots_unlocked:
            return fail("Слот закритий.")
        w = svc.draft_world(request["uid"], slot, prof.name)
        leagues = []
        for lid, meta in LEAGUES.items():
            clubs = sorted(w.division_clubs(lid), key=lambda c: -team_rating(w, c) * 100 - c.reputation)
            leagues.append({"id": lid, "name": meta["name"], "short": meta["short"], "flag": meta["flag"],
                            "clubs": [{**club_json(w, c), "rating": team_rating(w, c), "budget": c.budget,
                                       "profile": club_profile(w, c, i + 1, len(clubs))}
                                      for i, c in enumerate(clubs)]})
        return ok({"slot": slot, "leagues": leagues})

    async def career_create(request):
        b = await body(request)
        prof = sync_user(request)
        try:
            svc.create_career(request["uid"], int(b.get("slot", 0)), int(b["club_id"]), prof.name)
        except (ValueError, KeyError) as e:
            return fail(str(e))
        return ok(profile_json(svc, request["uid"]), "Вітаємо з призначенням!")

    async def career_select(request):
        slot = int((await body(request)).get("slot", 0))
        prof = svc.st.profile(request["uid"])
        if svc.st.load(request["uid"], slot) is None:
            return fail("Слот порожній.")
        prof.active_slot = slot
        svc.st.save_profile(prof)
        return ok(profile_json(svc, request["uid"]))

    async def career_delete(request):
        slot = int((await body(request)).get("slot", 0))
        svc.st.delete(request["uid"], slot)
        return ok(profile_json(svc, request["uid"]), "Кар’єру видалено.")

    # ---------------- in-career views
    async def get_team(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        return ok(team_json(w))

    async def get_match(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        return ok(match_preview(w))

    async def play_match(request):
        w, prof = world(request)
        if w is None or w.fired:
            return fail("Немає активної кар’єри.")
        level_before = prof.rank[1]
        b = await body(request)
        if not b.get("fast"):
            sim = svc.first_half(w)
            if sim is None:
                return fail("Сезон завершено.")
            svc.st.save(w)
            return ok(halftime_json(w, sim))
        res = svc.play(w, prof)
        if res is None:
            return fail("Сезон завершено.")
        svc.st.save(w)
        svc.st.save_profile(prof)
        if prof.rank[1] > level_before:
            from ..bot.messages import level_up
            await svc.send(request["uid"], level_up(prof))
        return ok(match_result_json(w, res))

    async def second_half(request):
        w, prof = world(request)
        if w is None or not w.pending:
            return fail("Немає матчу на паузі.")
        b = await body(request)
        level_before = prof.rank[1]
        subs = [(int(a), int(c)) for a, c in (b.get("subs") or [])][:5]
        res = svc.second_half(w, prof, str(b.get("talk", "")), str(b.get("style", "")), subs)
        if res is None:
            return fail("Немає матчу на паузі.")
        svc.st.save(w)
        svc.st.save_profile(prof)
        if prof.rank[1] > level_before:
            from ..bot.messages import level_up
            await svc.send(request["uid"], level_up(prof))
        return ok(match_result_json(w, res))

    async def press_answer(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        from ..game.events import answer_press
        good, msg = answer_press(w, str((await body(request)).get("answer", "")))
        if not good:
            return fail(msg)
        svc.st.save(w)
        return ok(life_json(w), msg)

    async def dilemma_answer(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        b = await body(request)
        from ..game.events import resolve_dilemma
        good, msg = resolve_dilemma(w, int(b.get("id", 0)), str(b.get("option", "")))
        if not good:
            return fail(msg)
        svc.st.save(w)
        return ok(life_json(w), msg)

    async def get_records(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        return ok(records_json(w))

    async def get_staff(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        return ok(staff_json(w))

    async def staff_action(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        b = await body(request)
        from ..game import staff as stf
        if b.get("action") == "fire":
            good, msg = stf.fire(w, str(b.get("role", "")))
        else:
            good, msg = stf.hire(w, str(b.get("role", "")), str(b.get("id", "")))
        if not good:
            return fail(msg)
        svc.st.save(w)
        return ok(staff_json(w), msg)

    async def get_finance(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        out = finance_json(w)
        svc.st.save(w)
        return ok(out)

    async def sponsor_sign(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        from ..game import sponsors as sp
        good, msg = sp.sign(w, str((await body(request)).get("id", "")))
        if not good:
            return fail(msg)
        svc.st.save(w)
        return ok(finance_json(w), msg)

    async def get_calendar(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        cupsmod.ensure(w)
        return ok(calendar_json(w))

    async def get_totw(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        return ok(totw_json(w) or {"empty": True})

    async def get_jobs(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        return ok(jobs_json(w))

    async def post_jobs(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        from ..game import career
        b = await body(request)
        if b.get("decline"):
            good, msg = career.decline_all(w)
        else:
            good, msg = career.accept(w, int(b.get("club", 0)))
        if not good:
            return fail(msg)
        svc.st.save(w)
        return ok(jobs_json(w), msg)

    async def get_loans(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        return ok(loans_json(w))

    async def get_ballon(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        return ok({"history": [{**b, "top": [{**t, "club": club_json(w, w.clubs[t["club"]]), "flag": flag(t["nation"])}
                                             for t in b["top"]]} for b in w.ballon]})

    async def get_friends(request):
        return ok(friends_json(svc, request["uid"]))

    async def weekly_claim(request):
        uid = request["uid"]
        async with locks[uid]:
            prof = svc.st.profile(uid)
            good, msg = prof.claim_weekly(str((await body(request)).get("id", "")))
            if not good:
                return fail(msg)
            svc.st.save_profile(prof)
        return ok(friends_json(svc, uid), msg)

    async def friendly(request):
        uid = request["uid"]
        fid = int((await body(request)).get("uid", 0))
        good, msg, res = svc.friendly(uid, fid)
        if not good:
            return fail(msg)
        await svc.send(fid, f"🤝 <b>{res['home'].name}</b> {res['hg']}:{res['ag']} <b>{res['away'].name}</b>\n"
                            f"Твій друг зіграв проти тебе товариський матч. Відкрий гру і візьми реванш!")
        res["home"], res["away"] = club_json(None, res["home"]), club_json(None, res["away"])
        return ok(res, msg)

    async def season_end(request):
        w, prof = world(request)
        if w is None or not season_over(w):
            return fail("Сезон ще триває.")
        level_before = prof.rank[1]
        s = svc.finish_season(w, prof)
        svc.st.save(w)
        svc.st.save_profile(prof)
        from ..bot.messages import season_report
        await svc.send(request["uid"], season_report(s, prof, level_before))
        div = s["division"]
        out = {"season": season_label(s["season"]), "position": s["position"], "target": s["target"],
               "league": LEAGUES[div]["short"], "prize": s.get("prize", 0), "xp": s["xp"], "fired": w.fired,
               "confidence": w.confidence, "newTarget": w.board_target,
               "promoted": [w.clubs[c].name for c in s.get("promoted", [])],
               "relegated": [w.clubs[c].name for c in s.get("relegated", [])],
               "retired": s.get("retired", []), "left": s.get("left", []),
               "youth": [w.players[i].name for i in s.get("youth", []) if i in w.players],
               "jobs": s.get("jobs", 0), "awards": s.get("awards"), "sponsorNews": (s.get("sponsor") or []) + (s.get("loans") or []),
               "ballon": {**s["ballon"], "top": [{**t, "club": club_json(w, w.clubs[t["club"]]), "flag": flag(t["nation"])}
                                                 for t in s["ballon"]["top"]]} if s.get("ballon") else None,
               "champions": [{"league": LEAGUES[int(d)]["short"], "club": w.clubs[i["champion"]].name}
                             for d, i in s["divisions"].items()]}
        return ok(out)

    async def get_table(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        league = int(request.query.get("league", w.club.division))
        if league not in LEAGUES:
            league = w.club.division
        return ok(table_json(w, league))

    async def get_market(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        q = request.query
        return ok(market_json(w, q.get("f", "ALL"), int(q.get("page", 0)), q.get("q", "").strip()))

    async def get_player(request):
        w, _ = world(request)
        pid = int(request.query.get("id", 0))
        if w is None or pid not in w.players:
            return fail("Гравця не знайдено.", 404)
        return ok(player_detail(w, pid))

    async def player_action(request):
        w, prof = world(request)
        b = await body(request)
        pid, action = int(b.get("id", 0)), b.get("action")
        from ..game import loans as ln
        if w is not None and pid in w.players and action in ("loan_in", "loan_out"):
            good, msg = (ln.loan_in if action == "loan_in" else ln.loan_out)(w, pid)
            if good:
                svc.st.save(w)
            return ok(player_detail(w, pid), msg) if good else fail(msg)
        if w is not None and pid in w.players and w.players[pid].loan and action in (
                "list", "renew", "release", "quicksell", "setlist"):
            return fail("Гравець в оренді: це можна зробити лише з власними гравцями.")
        if w is not None and pid in w.players and action in ("bid", "setlist", "train"):
            extra = None
            if action == "bid":
                good, msg, extra = tr.bid(w, pid, int(b.get("fee", 0)))
                svc.st.save(w)
                data = player_detail(w, pid)
                data["negotiation"] = extra
                return ok(data, msg) if good or extra.get("status") == "counter" else \
                    web.json_response({"ok": False, "error": msg, "data": data}, status=400)
            if action == "setlist":
                good, msg = tr.set_listing(w, pid, int(b["price"]) if b.get("price") else None)
            else:
                good, msg, cost = tr.train_player(w, pid)
                if good and prof.coins < cost:
                    good, msg = False, f"Потрібно {cost} монет."
                if good:
                    pl = w.players[pid]
                    prof.coins -= cost
                    pl.skill += 1
                    pl.trained = w.season * 1000 + w.round
                    svc.st.save_profile(prof)
                    msg = f"🏋️ {pl.name}: майстерність {pl.skill} (−{cost} монет)"
            if good:
                svc.st.save(w)
            return ok(player_detail(w, pid), msg) if good else fail(msg)
        fns = {"rest": tr.toggle_rest, "list": tr.toggle_list, "renew": tr.renew, "release": tr.release,
               "quicksell": tr.quick_sell, "buy": tr.buy}
        if w is None or action not in fns or pid not in w.players:
            return fail("Невірна дія.")
        p = w.players[pid]
        if action != "buy" and p.club_id != w.club_id:
            return fail("Гравця вже немає в клубі.")
        good, msg = fns[action](w, pid)
        if good:
            svc.st.save(w)
        data = player_detail(w, pid) if pid in w.players else None
        return ok(data, msg) if good else fail(msg)

    async def offer_action(request):
        w, _ = world(request)
        b = await body(request)
        oid = int(b.get("id", 0))
        if b.get("pitch"):
            good, msg = (tr.accept_pitch if b.get("accept") else tr.decline_pitch)(w, oid)
        elif b.get("counter"):
            good, msg = tr.counter_offer(w, oid, int(b["counter"]))
        else:
            good, msg = (tr.accept_offer if b.get("accept") else tr.reject_offer)(w, oid)
        if good:
            svc.st.save(w)
        return ok(market_json(w, "ALL", 0, ""), msg) if good else fail(msg)

    async def set_tactics(request):
        w, _ = world(request)
        b = await body(request)
        if b.get("formation") in FORMATIONS:
            w.club.formation = b["formation"]
        if b.get("style") in STYLES:
            w.club.style = b["style"]
        if b.get("training") in TRAINING:
            w.training = b["training"]
        svc.st.save(w)
        return ok(team_json(w))

    async def get_lineup(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        return ok(lineup_json(w))

    async def post_lineup(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        good, msg = lineup_action(w, await body(request))
        if good:
            svc.st.save(w)
            return ok(lineup_json(w), msg)
        return fail(msg or "Помилка.")

    async def get_cups(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        cupsmod.ensure(w)
        return ok(cups_json(w))

    async def cup_seen(request):
        w, _ = world(request)
        b = await body(request)
        comp = (w.cups or {}).get(b.get("key", ""))
        if comp:
            i = cupsmod.next_stage(comp)
            if i is not None:
                comp["seen"] = max(comp.get("seen", -1), i)
                svc.st.save(w)
        return ok(None)

    async def get_club(request):
        w, _ = world(request)
        if w is None:
            return fail("Немає активної кар’єри.", 404)
        return ok(club_tab_json(w))

    async def club_action(request):
        w, _ = world(request)
        b = await body(request)
        msg = None
        if "ticket" in b:
            w.club.ticket_price = max(3, min(300, w.club.ticket_price + int(b["ticket"])))
            good = True
        else:
            good, msg = tr.upgrade(w, b.get("upgrade", ""))
        if good:
            svc.st.save(w)
            return ok(club_tab_json(w), msg)
        return fail(msg)

    r.add_get("/api/profile", get_profile)
    r.add_post("/api/daily", claim_daily)
    r.add_post("/api/task", claim_task)
    r.add_post("/api/slot/unlock", unlock_slot)
    r.add_post("/api/shop", shop_buy)
    r.add_post("/api/career/draft", career_draft)
    r.add_post("/api/career/create", career_create)
    r.add_post("/api/career/select", career_select)
    r.add_post("/api/career/delete", career_delete)
    r.add_get("/api/team", get_team)
    r.add_get("/api/match", get_match)
    r.add_post("/api/match/play", play_match)
    r.add_post("/api/season/end", season_end)
    r.add_post("/api/match/second", second_half)
    r.add_post("/api/press", press_answer)
    r.add_post("/api/dilemma", dilemma_answer)
    r.add_get("/api/records", get_records)
    r.add_get("/api/staff", get_staff)
    r.add_post("/api/staff", staff_action)
    r.add_get("/api/friends", get_friends)
    r.add_get("/api/finance", get_finance)
    r.add_post("/api/sponsor", sponsor_sign)
    r.add_get("/api/ballon", get_ballon)
    r.add_get("/api/calendar", get_calendar)
    r.add_get("/api/totw", get_totw)
    r.add_get("/api/loans", get_loans)
    r.add_get("/api/jobs", get_jobs)
    r.add_post("/api/jobs", post_jobs)
    r.add_post("/api/weekly", weekly_claim)
    r.add_post("/api/friendly", friendly)
    r.add_get("/api/table", get_table)
    r.add_get("/api/market", get_market)
    r.add_get("/api/player", get_player)
    r.add_post("/api/player", player_action)
    r.add_post("/api/offer", offer_action)
    r.add_post("/api/tactics", set_tactics)
    r.add_get("/api/club", get_club)
    r.add_get("/api/lineup", get_lineup)
    r.add_get("/api/cups", get_cups)
    r.add_post("/api/cup/seen", cup_seen)
    r.add_post("/api/lineup", post_lineup)
    r.add_post("/api/club", club_action)

    async def index(request):
        resp = web.FileResponse(STATIC / "index.html")
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    async def crest_img(request):
        got = svc.st.crest_get(request.match_info["key"])
        if not got:
            raise web.HTTPNotFound()
        return web.Response(body=got[1], content_type=got[0], headers={"Cache-Control": "public, max-age=604800"})

    async def debug_crests(request):
        from ..game.leagues import CLUBS
        out = []
        for lid, clubs in CLUBS.items():
            for name, _, _, _, key in clubs:
                out.append({"league": LEAGUES[lid]["short"], "club": name, "key": key,
                            "stored": key in CREST_IMG, "status": CREST_STATUS.get(key, "not checked yet")})
        return web.json_response({"stored": sum(o["stored"] for o in out), "total": len(out), "clubs": out},
                                 dumps=lambda o: json.dumps(o, ensure_ascii=False))

    async def health(request):
        return web.Response(text="ok")

    r.add_get("/", index)
    r.add_get("/health", health)
    r.add_get("/crest/{key}", crest_img)
    r.add_get("/debug/crests", debug_crests)
    r.add_static("/static/", STATIC)
    return app
