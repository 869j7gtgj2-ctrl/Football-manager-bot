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
    if p.loan:
        return False, f"{p.name} грає тут в оренді: трансфер неможливий до кінця сезону."
    lvl = club_level(world.club.reputation)
    if p.skill > lvl + 14:
        return False, f"{p.name} вважає, що {world.club.name} недостатньо амбітний клуб для нього."
    return True, ""


def buy(world: World, pid: int, fee: int | None = None) -> tuple[bool, str]:
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
    fee = asking_price(world, pid) if fee is None else fee
    if world.club.budget < fee:
        return False, f"Не вистачає коштів: потрібно {money(fee)}."
    seller = world.clubs[p.club_id]
    world.club.budget -= fee
    seller.budget += fee
    world.season_finances["transfers_out"] += fee
    from .finance import book
    book(world, "transfers", fee, f"Купівля: {p.name} ({seller.name})")
    p.club_id = world.club_id
    p.wage = wage_demand(world, pid)
    p.contract = 3
    p.listed = p.resting = False
    p.morale = min(100, p.morale + 10)
    world.negotiations.pop(str(pid), None)
    world.pitches = [x for x in world.pitches if x["pid"] != pid]
    world.add_news(f"✍️ Підписано {p.name} з {seller.name} за {money(fee)}.")
    return True, f"✅ {p.name} тепер гравець {world.club.name}! Сума: {money(fee)}, зарплата {money(p.wage)}/тиж."


def round_fee(v: float) -> int:
    step = 100_000 if v >= 2_000_000 else 5000
    return max(step, int(round(v / step)) * step)


def bid(world: World, pid: int, fee: int) -> tuple[bool, str, dict]:
    """Haggling with the selling club. Returns (deal_done, message, {"status", "counter"})."""
    p = world.players.get(pid)
    if not p or p.club_id in (None, world.club_id):
        return False, "Гравця не знайдено.", {"status": "error"}
    if not world.transfer_window_open():
        return False, "Трансферне вікно закрите.", {"status": "error"}
    ok, why = will_join(world, pid)
    if not ok:
        return False, why, {"status": "error"}
    if world.club.budget < fee:
        return False, f"Не вистачає коштів: у бюджеті {money(world.club.budget)}.", {"status": "error"}
    seller = world.clubs[p.club_id]
    ask = asking_price(world, pid)
    neg = world.negotiations.setdefault(str(pid), {"n": 0, "counter": 0})
    if fee >= ask * 0.985 or (neg["counter"] and fee >= neg["counter"]):
        good, msg = buy(world, pid, fee)
        return good, msg, {"status": "accepted" if good else "error"}
    neg["n"] += 1
    if neg["n"] > 3:
        return False, f"{seller.name} втомився від торгу і закрив переговори до кінця вікна.", {"status": "closed"}
    if fee < ask * 0.6:
        return False, f"{seller.name}: «Це навіть не пропозиція». Спробуй ближче до {money(round_fee(ask * 0.9))}.", \
            {"status": "rejected"}
    floor = ask * (1 - 0.04 * neg["n"])  # the seller softens a little with every round
    counter = round_fee(max(fee * 1.03, (fee + floor) / 2))
    if neg["counter"]:
        counter = min(counter, neg["counter"])
    neg["counter"] = counter
    left = 3 - neg["n"]
    return False, f"{seller.name} хоче {money(counter)}. Можна погодитися або торгуватися далі (спроб: {left}).", \
        {"status": "counter", "counter": counter, "left": left}


def set_listing(world: World, pid: int, price: int | None) -> tuple[bool, str]:
    p = world.players.get(pid)
    if not p or p.club_id != world.club_id:
        return False, "Гравця не знайдено."
    if price is None or price <= 0:
        p.listed, p.ask = False, 0
        world.offers = [o for o in world.offers if o.player_id != pid]
        return True, "Знято з трансферного списку."
    p.listed, p.ask = True, round_fee(price)
    p.morale = max(10, p.morale - 5)
    ratio = p.ask / max(1, p.value())
    hint = "Ціна приваблива, покупці знайдуться швидко." if ratio <= 1 else \
        "Ціна висока, пропозицій буде менше." if ratio <= 1.4 else "Ціна дуже висока, навряд чи хтось заплатить."
    return True, f"🏷 {p.name} на продажі за {money(p.ask)}. {hint}"


def counter_offer(world: World, offer_id: int, fee: int) -> tuple[bool, str]:
    o = next((x for x in world.offers if x.id == offer_id), None)
    if not o:
        return False, "Пропозиція вже неактуальна."
    buyer = world.clubs[o.club_id]
    cap = o.max_fee or o.fee
    if fee <= cap:
        o.fee = round_fee(fee)
        return sell_to(world, o.player_id, o.club_id, o.fee)
    if o.kind == "final":
        world.offers = [x for x in world.offers if x.id != offer_id]
        return True, f"{buyer.name} відмовився від угоди: забагато."
    o.fee = round_fee(min(cap, (o.fee + fee) / 2))
    o.kind = "final"
    return True, f"{buyer.name} піднімає пропозицію до {money(o.fee)}. Це їхня остання ціна."


def accept_pitch(world: World, pitch_id: int) -> tuple[bool, str]:
    pt = next((x for x in world.pitches if x["id"] == pitch_id), None)
    if not pt:
        return False, "Пропозиція агента вже неактуальна."
    good, msg = buy(world, pt["pid"], pt["fee"])
    if good:
        world.pitches = [x for x in world.pitches if x["id"] != pitch_id]
    return good, msg


def decline_pitch(world: World, pitch_id: int) -> tuple[bool, str]:
    world.pitches = [x for x in world.pitches if x["id"] != pitch_id]
    return True, "Агенту відмовлено."


def generate_pitches(world: World, rng: random.Random) -> None:
    """Agents call while the window is open, offering players that fit the squad's weak spots."""
    world.pitches = [x for x in world.pitches if x["until"] >= world.round and x["pid"] in world.players
                     and world.players[x["pid"]].club_id not in (None, world.club_id)]
    if not world.transfer_window_open():
        world.pitches = []
        return
    if len(world.pitches) >= 3 or rng.random() > 0.6:
        return
    squad = world.squad(world.club_id)
    if not squad:
        return
    lines = {}
    for p in squad:
        lines.setdefault(p.pos, []).append(p.skill)
    need = min(("GK", "DF", "MF", "FW"), key=lambda k: (sorted(lines.get(k, [0]), reverse=True)[:3] or [0])[-1])
    avg = sorted((p.skill for p in squad), reverse=True)[:11]
    avg = sum(avg) / max(1, len(avg))
    taken = {x["pid"] for x in world.pitches}
    cands = [p for p in world.players.values() if p.club_id not in (None, world.club_id) and p.pos == need
             and avg - 2 <= p.skill <= avg + 8 and p.id not in taken and will_join(world, p.id)[0]]
    cands = [p for p in cands if asking_price(world, p.id) * 0.85 <= world.club.budget * 1.15]
    if not cands:
        return
    p = rng.choice(sorted(cands, key=lambda x: -x.skill)[:12])
    fee = round_fee(asking_price(world, p.id) * rng.uniform(0.8, 0.93))
    notes = ["Клуб готовий відпустити його зі знижкою.", "Гравець хоче нового виклику і чекає твого дзвінка.",
             "У нього конфлікт з тренером, ціна нижча за ринкову.", "Ексклюзивна пропозиція: діє лише кілька турів."]
    world.pitches.append({"id": world.new_id(), "pid": p.id, "fee": fee, "until": world.round + 3,
                          "note": rng.choice(notes)})
    world.add_news(f"📞 Агент пропонує {p.name} ({world.clubs[p.club_id].name}) за {money(fee)}.")


def train_player(world: World, pid: int) -> tuple[bool, str, int]:
    """Paid individual session (costs coins in the service layer): +1 skill once per round, up to potential."""
    p = world.players.get(pid)
    if not p or p.club_id != world.club_id:
        return False, "Гравця не знайдено.", 0
    stamp = world.season * 1000 + world.round
    if p.trained == stamp:
        return False, "Цей гравець уже тренувався в цьому турі.", 0
    if p.skill >= min(99, p.potential):
        return False, f"{p.name} досяг свого потенціалу.", 0
    return True, "", training_cost(p)


def training_cost(p) -> int:
    return 6 + max(0, p.skill - 50) // 3


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
    from .finance import book
    book(world, "bonus", bonus, f"Бонус за підпис: {p.name}")
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
    from .finance import book
    book(world, "sales", fee, f"Продаж: {p.name} ({buyer.name})")
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
    from .finance import book
    book(world, "comp", comp, f"Розірвання контракту: {p.name}")
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
    if not p.listed:
        return set_listing(world, pid, p.value())
    p.listed, p.ask = False, 0
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
    from .finance import book
    book(world, "infra", cost, {"stadium": "Розширення стадіону", "training": "Тренувальна база",
                                "academy": "Академія"}.get(kind, kind))
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
