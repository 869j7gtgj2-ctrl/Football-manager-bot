"""Season-long loans in both directions. A loaned player sits at the borrowing club (club_id) and keeps
his parent club in Player.loan; everyone returns home at the end of the season."""
from __future__ import annotations

import random

from .generator import club_level
from .leagues import LEAGUES
from .models import SQUAD_MAX, SQUAD_MIN, World


def loan_fee(p) -> int:
    return max(10_000, int(p.value() * 0.08 / 5000) * 5000)


def can_loan_in(w: World, pid: int) -> tuple[bool, str]:
    p = w.players.get(pid)
    if not p or not p.club_id or p.club_id == w.club_id:
        return False, "Цього гравця не можна орендувати."
    if p.loan:
        return False, "Гравець уже в оренді."
    if not w.transfer_window_open():
        return False, "Трансферне вікно закрите."
    if len(w.squad(w.club_id)) >= SQUAD_MAX:
        return False, f"У складі вже {SQUAD_MAX} гравців."
    parent = w.squad(p.club_id)
    ranked = sorted(parent, key=lambda x: -x.skill)
    if p in ranked[:11] or (p in ranked[:14] and p.age > 21):
        return False, f"{w.clubs[p.club_id].name} не віддає основних гравців в оренду."
    if p.skill > club_level(w.club.reputation) + 14:
        return False, f"{p.name} не хоче йти в клуб такого рівня."
    if w.club.budget < loan_fee(p):
        return False, "Не вистачає коштів на орендну плату."
    return True, ""


def loan_in(w: World, pid: int) -> tuple[bool, str]:
    good, why = can_loan_in(w, pid)
    if not good:
        return False, why
    p = w.players[pid]
    fee = loan_fee(p)
    parent = w.clubs[p.club_id]
    w.club.budget -= fee
    parent.budget += fee
    w.season_finances["transfers_out"] += fee
    from .finance import book
    book(w, "transfers", fee, f"Оренда: {p.name} з {parent.name}")
    p.loan = parent.id
    p.club_id = w.club_id
    p.listed = p.resting = False
    p.morale = min(100, p.morale + 5)
    w.add_news(f"🔁 {p.name} ({p.skill}) прибув в оренду з {parent.name} до кінця сезону.")
    return True, f"🔁 {p.name} у команді до кінця сезону. Орендна плата {fee:,} €.".replace(",", " ")


def loan_out_targets(w: World, p) -> list:
    """AI clubs where the player would be a starter: lower or equal level, ideally same country."""
    nation = LEAGUES[w.club.division]["nation"]
    out = []
    for c in w.clubs.values():
        if c.is_user or len(w.squad(c.id)) >= 28:
            continue
        mates = sorted((x.skill for x in w.squad(c.id) if x.pos == p.pos), reverse=True)
        starters = {"GK": 1, "DF": 5, "MF": 5, "FW": 3}[p.pos]
        bar = mates[starters - 1] if len(mates) >= starters else 0
        if p.skill + 3 >= bar and club_level(c.reputation) + 12 >= p.skill:
            out.append((0 if LEAGUES[c.division]["nation"] == nation else 1, -c.reputation, c))
    out.sort(key=lambda t: t[:2])
    return [c for *_, c in out]


def loan_out(w: World, pid: int, rng: random.Random | None = None) -> tuple[bool, str]:
    p = w.players.get(pid)
    if not p or p.club_id != w.club_id:
        return False, "Гравця не знайдено."
    if p.loan:
        return False, "Орендованого гравця не можна передати далі."
    if not w.transfer_window_open():
        return False, "Трансферне вікно закрите."
    if len(w.squad(w.club_id)) <= SQUAD_MIN + 2:
        return False, "Замало гравців у складі."
    targets = loan_out_targets(w, p)
    if not targets:
        return False, f"Жоден клуб не гарантує {p.name} ігрового часу."
    rng = rng or random.Random()
    club = rng.choice(targets[:4])
    p.loan = w.club_id
    p.club_id = club.id
    p.listed = p.resting = False
    if w.captain == p.id:
        w.captain = None
    w.lineups = {k: [None if x == p.id else x for x in v] for k, v in (w.lineups or {}).items()}
    w.add_news(f"✈️ {p.name} поїхав в оренду в {club.name} ({LEAGUES[club.division]['short']}).")
    return True, f"✈️ {p.name} до кінця сезону грає за {club.name}. Зарплату платить орендар."


def loaned_out(w: World) -> list:
    return [p for p in w.players.values() if p.loan == w.club_id and p.club_id != w.club_id]


def loaned_in(w: World) -> list:
    return [p for p in w.squad(w.club_id) if p.loan]


def return_all(w: World) -> list[str]:
    """Season end, before stats reset: everybody goes home; game time abroad gives a growth bonus."""
    lines = []
    for p in list(w.players.values()):
        if not p.loan:
            continue
        parent = p.loan
        mine_out = parent == w.club_id
        if mine_out and p.apps >= 12 and p.skill < p.potential:
            p.skill = min(p.potential, p.skill + 1 + (p.apps >= 24))
            lines.append(f"{p.name} повернувся з оренди сильнішим: {p.skill} ({p.apps} матчів, {p.goals} гол.).")
        elif mine_out:
            lines.append(f"{p.name} повернувся з оренди ({p.apps} матчів).")
        p.club_id = parent if parent in w.clubs else None
        p.loan = 0
        p.listed = p.resting = False
    return lines
