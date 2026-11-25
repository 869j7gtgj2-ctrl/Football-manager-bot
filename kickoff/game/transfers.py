"""User-facing club management actions. Each returns (ok, message)."""
from __future__ import annotations

import random

from .generator import club_level
from .models import SQUAD_MAX, SQUAD_MIN, World


def asking_price(world: World, pid: int) -> int:
    p = world.players[pid]
    if p.club_id is None:
        return 0
    seller = world.clubs[p.club_id]
    squad = sorted(world.squad(seller.id), key=lambda x: x.skill, reverse=True)
    key = p.id in [x.id for x in squad[:4]]
    k = 1.15 + (0.3 if key else 0) + (0.15 if p.contract >= 3 else 0) - (0.2 if p.contract <= 1 else 0)
    return int(p.value() * k / 5000) * 5000


def wage_demand(world: World, pid: int) -> int:
    p = world.players[pid]
    return int(max(p.fair_wage(), p.wage * 1.15) / 50) * 50


def will_join(world: World, pid: int) -> tuple[bool, str]:
    p = world.players[pid]
    lvl = club_level(world.club.reputation)
    if p.skill > lvl + 14:
        return False, f"{p.name} вважає, що {world.club.name} недостатньо амбітний клуб для нього."
    return True, ""


def buy(world: World, pid: int) -> tuple[bool, str]:
    p = world.players.get(pid)
    if not p or p.club_id == world.club_id:
        return False, "Гравця не знайдено."
    if p.club_id is not None and not world.transfer_window_open():
        return False, "Трансферне вікно закрите. Вільних агентів можна підписувати будь-коли."
    if len(world.squad(world.club_id)) >= SQUAD_MAX:
        return False, f"У складі вже {SQUAD_MAX} гравців. Спершу когось продай."
    if p.club_id is None:
        return _sign_free(world, p)
    ok, why = will_join(world, pid)
    if not ok:
        return False, why
    fee = asking_price(world, pid)
    if world.club.budget < fee:
        return False, f"Не вистачає коштів: потрібно {money(fee)}."
    seller = world.clubs[p.club_id]
    world.club.budget -= fee
    seller.budget += fee
    world.season_finances["transfers_out"] += fee
    p.club_id = world.club_id
    p.wage = wage_demand(world, pid)
    p.contract = 3
    p.listed = p.resting = False
    p.morale = min(100, p.morale + 10)
    world.add_news(f"✍️ Підписано {p.name} з {seller.name} за {money(fee)}.")
    return True, f"✅ {p.name} тепер гравець {world.club.name}! Сума: {money(fee)}, зарплата {money(p.wage)}/тиж."


def _sign_free(world: World, p) -> tuple[bool, str]:
    if len(world.squad(world.club_id)) >= SQUAD_MAX:
        return False, f"У складі вже {SQUAD_MAX} гравців."
    ok, why = will_join(world, p.id)
    if not ok:
        return False, why
    wage = wage_demand(world, p.id)
    bonus = wage * 4
    if world.club.budget < bonus:
        return False, f"Потрібен бонус за підпис {money(bonus)}."
    world.club.budget -= bonus
    world.season_finances["transfers_out"] += bonus
    p.club_id = world.club_id
    p.wage = wage
    p.contract = 2
    world.add_news(f"✍️ Вільний агент {p.name} підписав контракт.")
    return True, f"✅ {p.name} підписав контракт на 2 сезони. Бонус {money(bonus)}, зарплата {money(wage)}/тиж."


def sell_to(world: World, pid: int, club_id: int, fee: int) -> tuple[bool, str]:
    p = world.players.get(pid)
    if not p or p.club_id != world.club_id:
        return False, "Гравця вже немає в клубі."
    if len(world.squad(world.club_id)) <= SQUAD_MIN:
        return False, f"Мінімум {SQUAD_MIN} гравців у складі."
    buyer = world.clubs[club_id]
    buyer.budget -= fee
    world.club.budget += fee
    world.season_finances["transfers_in"] += fee
    p.club_id = buyer.id
    p.listed = p.resting = False
    p.wage = max(p.wage, p.fair_wage())
    p.contract = max(p.contract, 2)
    world.offers = [o for o in world.offers if o.player_id != pid]
    world.add_news(f"💸 {p.name} проданий у {buyer.name} за {money(fee)}.")
    return True, f"✅ {p.name} проданий у {buyer.name} за {money(fee)}."


def accept_offer(world: World, offer_id: int) -> tuple[bool, str]:
    offer = next((o for o in world.offers if o.id == offer_id), None)
    if not offer:
        return False, "Пропозиція вже неактуальна."
    return sell_to(world, offer.player_id, offer.club_id, offer.fee)


def reject_offer(world: World, offer_id: int) -> tuple[bool, str]:
    offer = next((o for o in world.offers if o.id == offer_id), None)
    world.offers = [o for o in world.offers if o.id != offer_id]
    if offer:
        p = world.players.get(offer.player_id)
        if p and not p.listed:
            p.morale = max(10, p.morale - 5)
    return True, "Пропозицію відхилено."


def quick_sell(world: World, pid: int, rng: random.Random | None = None) -> tuple[bool, str]:
    rng = rng or random.Random()
    if not world.transfer_window_open():
        return False, "Трансферне вікно закрите."
    p = world.players.get(pid)
    if not p:
        return False, "Гравця не знайдено."
    fee = int(p.value() * 0.6 / 5000) * 5000
    buyers = [c for c in world.clubs.values() if not c.is_user and c.budget >= fee]
    if not buyers:
        return False, "Ніхто зараз не може собі дозволити цього гравця."
    return sell_to(world, pid, rng.choice(buyers).id, fee)


def release(world: World, pid: int) -> tuple[bool, str]:
    p = world.players.get(pid)
    if not p or p.club_id != world.club_id:
        return False, "Гравця не знайдено."
    if len(world.squad(world.club_id)) <= SQUAD_MIN:
        return False, f"Мінімум {SQUAD_MIN} гравців у складі."
    comp = int(p.wage * 11 * p.contract)
    world.club.budget -= comp
    world.season_finances["wages"] += comp
    p.club_id = None
    p.listed = p.resting = False
    world.add_news(f"📤 Контракт з {p.name} розірвано (компенсація {money(comp)}).")
    return True, f"Контракт розірвано. Компенсація: {money(comp)}."


def renew(world: World, pid: int) -> tuple[bool, str]:
    p = world.players.get(pid)
    if not p or p.club_id != world.club_id:
        return False, "Гравця не знайдено."
    if p.contract >= 4:
        return False, "Контракт і так довгий."
    if p.morale < 35:
        return False, f"{p.name} незадоволений і не хоче продовжувати контракт."
    new_wage = int(max(p.wage, p.fair_wage() * 1.1) / 50) * 50
    p.wage = new_wage
    p.contract += 2
    return True, f"✅ {p.name} продовжив контракт (+2 сезони). Нова зарплата: {money(new_wage)}/тиж."


def toggle_list(world: World, pid: int) -> tuple[bool, str]:
    p = world.players[pid]
    p.listed = not p.listed
    if p.listed:
        p.morale = max(10, p.morale - 5)
    return True, ("🏷 Виставлено на трансфер." if p.listed else "Знято з трансферного списку.")


def toggle_rest(world: World, pid: int) -> tuple[bool, str]:
    p = world.players[pid]
    p.resting = not p.resting
    return True, ("💤 Гравець не гратиме в наступних матчах." if p.resting else "✅ Гравець знову доступний для складу.")


# ---------------------------------------------------------------- facilities
def upgrade_cost(world: World, kind: str) -> int | None:
    c = world.club
    if kind == "stadium":
        return 300_000 + c.stadium * 15
    if kind == "training":
        return None if c.training_level >= 5 else 500_000 * c.training_level
    if kind == "academy":
        return None if c.academy_level >= 5 else 350_000 * c.academy_level
    return None


def upgrade(world: World, kind: str) -> tuple[bool, str]:
    cost = upgrade_cost(world, kind)
    if cost is None:
        return False, "Максимальний рівень."
    c = world.club
    if c.budget < cost:
        return False, f"Не вистачає коштів: потрібно {money(cost)}."
    c.budget -= cost
    world.season_finances["transfers_out"] += cost
    if kind == "stadium":
        c.stadium += 2500
        return True, f"🏟 Стадіон розширено до {c.stadium:,} місць.".replace(",", " ")
    if kind == "training":
        c.training_level += 1
        return True, f"🏋️ Тренувальна база: рівень {c.training_level}."
    c.academy_level += 1
    return True, f"🎓 Академія: рівень {c.academy_level}."


def money(v: int) -> str:
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000:
        return f"{sign}€{v / 1_000_000:.2f}M"
    if v >= 1000:
        return f"{sign}€{v / 1000:.0f}K"
    return f"{sign}€{v}"
