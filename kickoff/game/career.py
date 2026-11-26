"""Manager career: reputation, job offers from other clubs, and moving to a new club."""
from __future__ import annotations

import random

from .leagues import LEAGUES
from .models import World


def rep(w: World) -> int:
    r = w.records.get("mrep")
    if r is None:
        r = max(15, w.club.reputation - 8)
        w.records["mrep"] = r
    return r


def bump(w: World, delta: int, why: str | None = None) -> None:
    w.records["mrep"] = max(10, min(99, rep(w) + delta))
    if why:
        hist = w.records.setdefault("mrep_log", [])
        hist.insert(0, {"season": w.season, "d": delta, "why": why})
        del hist[12:]


def on_season_end(w: World, summary: dict, cups_won: list[str]) -> None:
    pos, target = summary["position"], summary["target"]
    if pos == 1:
        bump(w, 8, "Чемпіонство")
    elif pos <= target:
        bump(w, 2 + min(5, target - pos), f"Ціль виконана: {pos}-е місце")
    else:
        bump(w, -min(8, 2 + pos - target), f"Ціль провалена: {pos}-е місце при цілі топ-{target}")
    for name in cups_won:
        bump(w, 6, f"Трофей: {name}")
    if w.club_id in summary.get("promoted", []):
        bump(w, 5, "Підвищення в класі")
    if w.club_id in summary.get("relegated", []):
        bump(w, -8, "Виліт")


def _rounds(w: World, div: int) -> int:
    return len(w.fixtures.get(div, []))


def make_offers(w: World, rng: random.Random, kind: str) -> list[dict]:
    """kind: "season" (between seasons, any league), "fired" (must give at least one), "approach" (mid-season)."""
    r = rep(w)
    mid = w.round > 0
    lo, hi = (r - 25, r + 2) if kind == "fired" else (r - 6, r + 8)
    pool = []
    for c in w.clubs.values():
        if c.is_user or c.id == w.club_id:
            continue
        if mid and _rounds(w, c.division) != w.rounds_total:
            continue
        if kind != "fired" and c.reputation <= w.club.reputation:
            continue
        if lo <= c.reputation <= hi:
            pool.append(c)
    if kind == "fired" and not pool:
        pool = sorted((c for c in w.clubs.values() if not c.is_user
                       and (not mid or _rounds(w, c.division) == w.rounds_total)), key=lambda c: c.reputation)[:6]
    rng.shuffle(pool)
    n = {"season": rng.choice([0, 1, 1, 2, 3]), "fired": rng.choice([2, 3]), "approach": 1}[kind]
    if kind == "season" and r >= w.club.reputation + 4:
        n = max(n, 2)
    offers = []
    for c in pool[:n]:
        offers.append({"club": c.id, "kind": kind, "season": w.season, "round": w.round,
                       "target": _target(w, c), "budget": c.budget,
                       "pitch": rng.choice(PITCHES[kind]).format(club=c.name)})
    return offers


def _target(w: World, c) -> int:
    ranked = sorted(w.division_clubs(c.division), key=lambda x: x.reputation, reverse=True)
    return min(len(ranked), max(1, [x.id for x in ranked].index(c.id) + 1))


PITCHES = {
    "season": ["Президент {club} особисто зателефонував: «Нам потрібен саме ти».",
               "{club} готовий дати тобі повний контроль над трансферами.",
               "Спортивний директор {club} прилетів на переговори.",
               "{club} будує новий проєкт і бачить тебе його обличчям.",
               "Вболівальники {club} запустили петицію за твоє призначення."],
    "fired": ["{club} шукає тренера після провального старту і готовий дати шанс.",
              "Власник {club} вірить, що ти ще покажеш себе.",
              "{club} пропонує контракт: «У нас тобі ніхто не заважатиме»."],
    "approach": ["📞 Агент повідомляє: {club} хоче тебе просто зараз.",
                 "📞 {club} звільнив тренера і першим набрав саме тебе.",
                 "📞 Інсайдери пишуть: {club} уже готує для тебе контракт."],
}


def maybe_approach(w: World, rng: random.Random) -> None:
    if w.fired or w.records.get("jobs") or w.round < 4 or w.confidence < 55 or rng.random() > 0.035:
        return
    offers = make_offers(w, rng, "approach")
    if offers:
        offers[0]["until"] = w.round + 2
        w.records["jobs"] = offers
        w.add_news(f"📞 {w.clubs[offers[0]['club']].name} цікавиться тобою як тренером!")


def expire(w: World) -> None:
    jobs = w.records.get("jobs") or []
    keep = [j for j in jobs if w.fired or j["kind"] == "fired"
            or (j["kind"] == "approach" and j.get("until", 0) >= w.round)
            or (j["kind"] == "season" and j["season"] == w.season and w.round == 0)]
    w.records["jobs"] = keep


def accept(w: World, cid: int, rng: random.Random | None = None) -> tuple[bool, str]:
    jobs = w.records.get("jobs") or []
    job = next((j for j in jobs if j["club"] == cid), None)
    if not job or cid not in w.clubs:
        return False, "Ця пропозиція вже неактуальна."
    rng = rng or random.Random()
    old = w.club
    new = w.clubs[cid]
    if w.round > 0 and _rounds(w, new.division) != w.rounds_total:
        return False, "Цей клуб уже не чекає."
    old.is_user = False
    new.is_user = True
    w.club_id = cid
    w.fired = False
    w.confidence = 60
    w.lineups, w.captain, w.last_xi, w.active_lineup = {}, None, [], 1
    w.negotiations, w.pitches, w.offers, w.dilemmas = {}, [], [], []
    w.pending, w.press = {}, {}
    w.sponsor, w.sponsor_offers = {}, []
    w.records["jobs"] = []
    w.records.pop("_boost", None)
    for p in w.squad(old.id):
        p.listed = p.resting = False
    log = w.records.setdefault("career", [])
    log.insert(0, {"season": w.season, "round": w.round, "from": old.id, "to": cid})
    from . import sponsors
    from .season import board_target
    w.board_target = board_target(w)
    if w.round == 0:
        from . import cups
        cups.setup(w, rng)
    sponsors.on_season_start(w, rng)
    bump(w, 1 if new.reputation > old.reputation else 0)
    w.add_news(f"✍️ Ти новий головний тренер {new.name}! Ціль: топ-{w.board_target}.")
    return True, f"✍️ Вітаємо в {new.name} ({LEAGUES[new.division]['short']})! Правління чекає топ-{w.board_target}."


def decline_all(w: World) -> tuple[bool, str]:
    if w.fired:
        return False, "Без клубу кар'єра не продовжиться: обери одну з пропозицій."
    w.records["jobs"] = []
    w.confidence = min(100, w.confidence + 5)
    return True, "Ти залишаєшся. Правління і вболівальники оцінили відданість (+5 довіри)."


def on_fired(w: World, rng: random.Random) -> None:
    if any(j["kind"] == "fired" for j in w.records.get("jobs") or []):
        return
    bump(w, -10, "Звільнення")
    w.records["jobs"] = make_offers(w, rng, "fired")
