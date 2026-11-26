"""The user's season calendar (league + cups + Champions League) and the team of the week."""
from __future__ import annotations

from .models import World

TOTW_SHAPE = (("GK", 1), ("DF", 4), ("MF", 3), ("FW", 3))


def calendar(w: World) -> list[dict]:
    """Every match of the user's season in play order, played ones with the score."""
    me = w.club_id
    div = w.club.division
    out = []
    played = {(r.round, r.home, r.away): r for r in w.results if r.division == div}
    for k, pairs in enumerate(w.fixtures.get(div, [])):
        for h, a in pairs:
            if me in (h, a):
                r = played.get((k, h, a))
                out.append({"order": k * 10 + 5, "comp": "league", "label": f"Тур {k + 1}", "home": h, "away": a,
                            "hg": r.hg if r else None, "ag": r.ag if r else None, "played": bool(r)})
    for key, comp in (w.cups or {}).items():
        shown_future = False
        for i, st in enumerate(comp["stages"]):
            tie = next((t for t in st["ties"] if me in (t["a"], t["b"]) and t["b"] is not None), None)
            sub = 1 if key == "cup" else 2
            if tie:
                h, a = (tie["b"], tie["a"]) if st["type"] == "leg2" else (tie["a"], tie["b"])
                leg = tie["legs"][-1] if tie["legs"] else None
                out.append({"order": st["round"] * 10 + sub, "comp": key, "label": st["label"], "home": h, "away": a,
                            "hg": leg["hg"] if leg else None, "ag": leg["ag"] if leg else None, "played": bool(leg),
                            "pens": leg.get("pens") if leg else None, "agg": leg.get("agg") if leg else None})
            elif not st["done"] and not shown_future and me in comp.get("alive", []) and not st["ties"]:
                shown_future = True
                out.append({"order": st["round"] * 10 + sub, "comp": key, "label": st["label"], "home": None,
                            "away": None, "hg": None, "ag": None, "played": False, "tbd": True})
    out.sort(key=lambda e: e["order"])
    nxt = next((e for e in out if not e["played"] and not e.get("tbd")), None)
    if nxt:
        nxt["next"] = True
    return out


def team_of_week(w: World, ratings: dict, rnd: int) -> list[str]:
    """Pick a 4-3-3 of the best ratings in the user's league this round; returns news lines."""
    best = {}
    for pid, rt in ratings.items():
        p = w.players.get(int(pid))
        if p and p.club_id:
            best[p.id] = rt
    xi = []
    for pos, n in TOTW_SHAPE:
        cands = sorted((pid for pid in best if w.players[pid].pos == pos), key=lambda i: -best[i])[:n]
        xi += [{"pid": pid, "pos": pos, "rating": round(best[pid], 1), "club": w.players[pid].club_id} for pid in cands]
    if len(xi) < 11:
        return []
    star = max(xi, key=lambda x: x["rating"])
    w.totw = {"round": rnd, "season": w.season, "xi": xi, "star": star["pid"]}
    mine = [w.players[x["pid"]] for x in xi if x["club"] == w.club_id]
    counts = w.records.setdefault("totw", {})
    for p in mine:
        p.morale = min(100, p.morale + 4)
        counts[p.name] = counts.get(p.name, 0) + 1
    if not mine:
        return []
    names = ", ".join(p.name for p in mine[:3])
    return [f"⭐ Збірна туру {rnd}: {names}" + (" та інші" if len(mine) > 3 else "") + "."]
