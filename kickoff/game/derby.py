"""Derbies and historic rivalries: bigger crowds, bigger stakes, a head-to-head record."""
from __future__ import annotations

from .models import World

DERBIES = [
    ("Shakhtar Donetsk", "Dynamo Kyiv", "Класичне дербі України"),
    ("Dynamo Kyiv", "Karpaty Lviv", "Дербі Києва і Львова"),
    ("Dynamo Kyiv", "Obolon Kyiv", "Київське дербі"),
    ("Dynamo Kyiv", "Livyi Bereh", "Київське дербі"),
    ("Metalist 1925", "Metalist Kharkiv", "Харківське дербі"),
    ("Chornomorets Odesa", "Shakhtar Donetsk", "Дербі півдня і сходу"),
    ("arsenal", "tottenham", "Північнолондонське дербі"),
    ("liverpool", "everton", "Мерсісайдське дербі"),
    ("manchester united", "manchester city", "Манчестерське дербі"),
    ("manchester united", "liverpool", "Північно-західне дербі"),
    ("chelsea", "arsenal", "Лондонське дербі"),
    ("chelsea", "tottenham", "Лондонське дербі"),
    ("newcastle", "sunderland", "Дербі Тайну і Віру"),
    ("real madrid", "barcelona", "Ель Класіко"),
    ("real madrid", "atletico", "Мадридське дербі"),
    ("barcelona", "espanyol", "Каталонське дербі"),
    ("betis", "sevilla", "Севільське дербі"),
    ("athletic", "real sociedad", "Баскське дербі"),
    ("bayern", "dortmund", "Дер Класікер"),
    ("dortmund", "schalke", "Рурське дербі"),
    ("hamburger", "werder", "Північне дербі"),
    ("internazionale", "ac milan", "Дербі делла Мадоніна"),
    ("roma", "lazio", "Римське дербі"),
    ("juventus", "internazionale", "Дербі Італії"),
    ("juventus", "torino", "Туринське дербі"),
    ("saint-germain", "marseille", "Ле Класік"),
    ("saint-germain", "paris fc", "Паризьке дербі"),
    ("nice", "monaco", "Лазурне дербі"),
    ("lens", "lille", "Північне дербі"),
]
_INDEX = {frozenset((a, b)): name for a, b, name in DERBIES}


def name(w: World, a: int, b: int) -> str | None:
    ca, cb = w.clubs.get(a), w.clubs.get(b)
    if not ca or not cb or not ca.key or not cb.key:
        return None
    return _INDEX.get(frozenset((ca.key, cb.key)))


def record(w: World, opp: int) -> dict:
    return (w.records.get("derbies") or {}).get(str(opp), {"w": 0, "d": 0, "l": 0})


def rivals(w: World) -> list[int]:
    return [c.id for c in w.clubs.values() if c.id != w.club_id and name(w, w.club_id, c.id)]


def after_match(w: World, res: dict) -> str | None:
    """Stakes of a derby for the user's club; returns the derby name when it was one."""
    home = res["home"] == w.club_id
    opp = res["away"] if home else res["home"]
    dn = name(w, w.club_id, opp)
    if not dn:
        return None
    gf, ga = (res["hg"], res["ag"]) if home else (res["ag"], res["hg"])
    rec = w.records.setdefault("derbies", {}).setdefault(str(opp), {"w": 0, "d": 0, "l": 0})
    squad = w.squad(w.club_id)
    oname = w.clubs[opp].name
    if gf > ga:
        rec["w"] += 1
        w.confidence = min(100, w.confidence + 4)
        for p in squad:
            p.morale = min(100, p.morale + 5)
        w.add_news(f"🔥 {dn}: перемога над {oname} {gf}:{ga}! Місто наше.")
    elif gf < ga:
        rec["l"] += 1
        w.confidence = max(0, w.confidence - 4)
        for p in squad:
            p.morale = max(10, p.morale - 3)
        w.add_news(f"🔥 {dn}: болюча поразка від {oname} {gf}:{ga}.")
    else:
        rec["d"] += 1
    return dn
