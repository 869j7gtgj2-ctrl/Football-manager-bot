"""General sponsor contracts: three offers each season, three payments (advance, winter, final) and bonus terms."""
from __future__ import annotations

import random

from .finance import book
from .leagues import LEAGUES

BRANDS = {
    "UA": [("Kyivstar", "📱", "Зв’язок"), ("monobank", "🐈‍⬛", "Фінанси"), ("ПриватБанк", "🏦", "Фінанси"),
           ("Нова пошта", "📦", "Логістика"), ("Rozetka", "🛒", "Ритейл"), ("Епіцентр", "🏬", "Ритейл"),
           ("Укрнафта", "⛽", "Енергетика"), ("ДТЕК", "⚡", "Енергетика"), ("Моршинська", "💧", "Напої"),
           ("Lifecell", "📶", "Зв’язок"), ("ОККО", "⛽", "Енергетика"), ("Ajax Systems", "🛡", "Технології")],
    "INT": [("Emirates", "✈️", "Авіа"), ("Qatar Airways", "✈️", "Авіа"), ("Toyota", "🚗", "Авто"), ("BMW", "🚙", "Авто"),
            ("Mastercard", "💳", "Фінанси"), ("Visa", "💳", "Фінанси"), ("Red Bull", "🐂", "Напої"),
            ("Monster Energy", "⚡", "Напої"), ("Coca-Cola", "🥤", "Напої"), ("Samsung", "📱", "Технології"),
            ("Sony", "🎮", "Технології"), ("Heineken", "🍺", "Напої"), ("Etihad", "✈️", "Авіа"),
            ("Spotify", "🎧", "Медіа"), ("Puma", "🐆", "Спорт"), ("Adidas", "👟", "Спорт"), ("Nike", "✔️", "Спорт"),
            ("Jeep", "🚙", "Авто"), ("Audi", "🏎", "Авто"), ("Allianz", "🛡", "Страхування")],
}
KINDS = {
    "stable": ("Стабільний", "Лише гарантовані виплати, без ризику"),
    "conditional": ("Умовний", "Менше гарантій, великий бонус за результат"),
    "bonus": ("Бонусний", "Гарантія плюс бонуси за голи і перемоги"),
}
PARTS = ("Аванс", "Зима", "Фінал")


def season_value(w) -> int:
    """What a typical sponsor pays per season, scaled by league money and reputation."""
    from .season import sponsor_income
    return int(sponsor_income(w.club) * max(20, w.rounds_total) * .9 / 50_000) * 50_000


def _offer(w, rng: random.Random, brand, kind: str) -> dict:
    base = season_value(w) * rng.uniform(.85, 1.2)
    target = max(1, min(w.board_target, len(w.division_clubs(w.club.division))))
    o = {"id": f"{brand[0]}-{w.season}-{rng.randint(100, 999)}", "brand": brand[0], "icon": brand[1],
         "sector": brand[2], "kind": kind, "years": rng.choice([1, 1, 2, 3])}
    if kind == "stable":
        g = base
        o["bonus"] = None
    elif kind == "conditional":
        g = base * .7
        top = max(1, target - rng.choice([0, 1, 2]))
        o["bonus"] = {"type": "pos", "value": top, "amount": int(base * rng.uniform(.7, 1.1) / 50_000) * 50_000,
                      "text": f"за топ-{top} у лізі"}
    else:
        g = base * .8
        o["bonus"] = {"type": "wins", "value": None, "amount": int(base * .03 / 10_000) * 10_000,
                      "text": "за кожну перемогу"}
    split = (.4, .3, .3)
    o["parts"] = [int(g * k / 50_000) * 50_000 for k in split]
    o["max"] = sum(o["parts"]) + (o["bonus"]["amount"] * (20 if kind == "bonus" else 1) if o["bonus"] else 0)
    return o


def make_offers(w, rng: random.Random | None = None) -> None:
    rng = rng or random.Random()
    pool = list(BRANDS["UA" if LEAGUES[w.club.division].get("nation") == "UA" else "INT"])
    if w.club.reputation >= 70:
        pool += BRANDS["INT"]
    taken = {w.sponsor.get("brand")} if w.sponsor else set()
    brands = rng.sample([b for b in dict.fromkeys(pool) if b[0] not in taken], 3)
    kinds = ["stable", "conditional", "bonus"]
    rng.shuffle(kinds)
    w.sponsor_offers = [_offer(w, rng, b, k) for b, k in zip(brands, kinds)]
    if w.sponsor and w.sponsor.get("left", 0) <= 0:
        # the current partner offers a renewal with fresh terms
        cur = (w.sponsor["brand"], w.sponsor["icon"], w.sponsor["sector"])
        ren = _offer(w, rng, cur, w.sponsor["kind"])
        ren["renewal"] = True
        w.sponsor_offers.insert(0, ren)


def can_change(w) -> bool:
    return not w.sponsor or w.sponsor.get("left", 0) <= 0


def sign(w, oid: str) -> tuple[bool, str]:
    if not can_change(w):
        return False, "Контракт ще діє. Змінити спонсора можна після завершення сезону."
    o = next((x for x in w.sponsor_offers if x["id"] == oid), None)
    if not o:
        return False, "Пропозиція вже неактуальна."
    w.sponsor = {**o, "left": o["years"], "paid": [False, False, False], "received": 0, "wins": 0, "since": w.season}
    w.sponsor_offers = []
    pay(w, 0)
    w.add_news(f"🤝 Новий генеральний спонсор: {o['brand']}!")
    return True, f"{o['icon']} {o['brand']} тепер генеральний спонсор. Аванс €{o['parts'][0]:,} вже на рахунку.".replace(",", " ")


def pay(w, part: int) -> int:
    s = w.sponsor
    if not s or s["paid"][part]:
        return 0
    amount = s["parts"][part]
    s["paid"][part] = True
    s["received"] += amount
    w.club.budget += amount
    w.season_finances["income"] += amount
    book(w, "sponsor", amount, f"{s['brand']}: {PARTS[part].lower()}")
    return amount


def on_round(w) -> None:
    """Called after each league round of the user's division."""
    s = w.sponsor
    if not s:
        return
    if w.round >= max(1, w.rounds_total // 2):
        pay(w, 1)


def on_win(w) -> None:
    s = w.sponsor
    if s and s.get("bonus") and s["bonus"]["type"] == "wins":
        amt = s["bonus"]["amount"]
        s["wins"] += 1
        s["received"] += amt
        w.club.budget += amt
        w.season_finances["income"] += amt
        book(w, "sponsor", amt)


def on_season_end(w, position: int) -> list[str]:
    s = w.sponsor
    out = []
    if s:
        pay(w, 1)
        got = pay(w, 2)
        if got:
            out.append(f"{s['brand']}: фінальна виплата €{got:,}".replace(",", " "))
        b = s.get("bonus")
        if b and b["type"] == "pos" and position <= b["value"]:
            s["received"] += b["amount"]
            w.club.budget += b["amount"]
            w.season_finances["income"] += b["amount"]
            book(w, "sponsor", b["amount"], f"{s['brand']}: бонус {b['text']}")
            out.append(f"{s['brand']}: бонус €{b['amount']:,} {b['text']}!".replace(",", " "))
        s["left"] -= 1
        if s["left"] > 0:
            s["paid"] = [False, False, False]
    return out


def on_season_start(w, rng: random.Random | None = None) -> None:
    s = w.sponsor
    if s and s.get("left", 0) > 0:
        pay(w, 0)
        w.sponsor_offers = []
    else:
        make_offers(w, rng)
