"""Golden Ball: the best player of the season across all leagues, top-10 with points."""
from __future__ import annotations

from .leagues import LEAGUES
from .season import table


def compute(w) -> dict:
    champs = {table(w, d)[0]["club"] for d in w.fixtures}
    top3 = {r["club"] for d in w.fixtures for r in table(w, d)[:3]}
    cup_winners = {k: c.get("winner") for k, c in (w.cups or {}).items()}
    cands = []
    for p in w.players.values():
        if not p.club_id or p.apps < 10:
            continue
        c = w.clubs[p.club_id]
        tier = LEAGUES[c.division].get("tier", 1)
        score = (p.avg_rating - 6.2) * 420 + p.goals * (16 if p.pos == "FW" else 22) + p.assists * 11 + p.apps * 2
        score += max(0, p.skill - 70) * 9
        tags = []
        if c.id in champs:
            score += 160
            tags.append("Чемпіонат")
        elif c.id in top3:
            score += 50
        if cup_winners.get("cup") == c.id:
            score += 70
            tags.append("Кубок")
        if cup_winners.get("ucl") == c.id:
            score += 260
            tags.append("Ліга чемпіонів")
        if p.pos in ("GK", "DF"):
            score += 40
        score *= 1.0 if tier == 1 else .55
        cands.append((score, p, c, tags))
    cands.sort(key=lambda x: -x[0])
    top = []
    for i, (score, p, c, tags) in enumerate(cands[:10]):
        top.append({"rank": i + 1, "pid": p.id, "name": p.name, "pos": p.pos, "role": p.role, "age": p.age,
                    "club": c.id, "clubName": c.name, "goals": p.goals, "assists": p.assists, "apps": p.apps,
                    "rating": p.avg_rating, "points": max(10, int(score)), "tags": tags, "mine": c.id == w.club_id,
                    "nation": p.nation})
    entry = {"year": 2026 + w.season, "season": f"{2025 + w.season}/{str(2026 + w.season)[-2:]}", "top": top}
    w.ballon.insert(0, entry)
    del w.ballon[10:]
    if top and top[0]["mine"]:
        w.add_news(f"🏆 {top[0]['name']} виграв Золотий м’яч!")
    return entry
