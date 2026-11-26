"""Manager life between matches: press conferences, player dilemmas, club records and season awards."""
from __future__ import annotations

import random

from .models import World

from .press import answer_press, open_press  # noqa: F401  (re-exported)


# ---------------------------------------------------------------- records
def update_records(w: World, res: dict) -> list[str]:
    r = w.records
    home = res["home"] == w.club_id
    gf, ga = (res["hg"], res["ag"]) if home else (res["ag"], res["hg"])
    opp = w.clubs[res["away"] if home else res["home"]].name
    label = f"{2025 + w.season}/{str(2026 + w.season)[-2:]}"
    new = []
    for k in ("matches", "wins", "draws", "losses", "gf", "ga"):
        r.setdefault(k, 0)
    r["matches"] += 1
    r["gf"] += gf
    r["ga"] += ga
    r["wins" if gf > ga else "draws" if gf == ga else "losses"] += 1
    if gf > ga:
        bw = r.get("big_win")
        if not bw or gf - ga > bw["d"] or (gf - ga == bw["d"] and gf > bw["gf"]):
            r["big_win"] = {"d": gf - ga, "gf": gf, "ga": ga, "opp": opp, "season": label}
            if bw:
                new.append(f"Рекорд: найбільша перемога {gf}:{ga}!")
    if gf < ga:
        bl = r.get("big_loss")
        if not bl or ga - gf > bl["d"]:
            r["big_loss"] = {"d": ga - gf, "gf": gf, "ga": ga, "opp": opp, "season": label}
    r["streak"] = r.get("streak", 0) + 1 if gf >= ga else 0
    if r["streak"] > r.get("best_streak", 0):
        r["best_streak"] = r["streak"]
        if r["streak"] >= 5 and r["streak"] % 5 == 0:
            new.append(f"Рекорд клубу: {r['streak']} матчів без поразок!")
    sc = r.setdefault("scorers", {})
    for pid, g in res["goals_by"].items():
        p = w.players.get(int(pid))
        if p and p.club_id == w.club_id:
            sc[p.name] = sc.get(p.name, 0) + g
    ap = r.setdefault("apps", {})
    for pid in res["minutes"]:
        p = w.players.get(int(pid))
        if p and p.club_id == w.club_id:
            ap[p.name] = ap.get(p.name, 0) + 1
    if len(sc) > 60:
        r["scorers"] = dict(sorted(sc.items(), key=lambda kv: -kv[1])[:40])
    if len(ap) > 60:
        r["apps"] = dict(sorted(ap.items(), key=lambda kv: -kv[1])[:40])
    return new


def season_awards(w: World) -> dict:
    """Called before season stats are reset: awards for the user's league and the user's club."""
    div = w.club.division
    league = [p for p in w.players.values() if p.club_id and w.clubs[p.club_id].division == div]
    items = []

    def add(title, icon, p, value):
        if p:
            items.append({"title": title, "icon": icon, "name": p.name, "club": w.clubs[p.club_id].name,
                          "value": value, "mine": p.club_id == w.club_id})
    boot = max(league, key=lambda p: (p.goals, p.assists), default=None)
    add("Золота бутса", "👟", boot if boot and boot.goals else None, f"{boot.goals} гол." if boot else "")
    reg = [p for p in league if p.apps >= 8]
    mvp = max(reg, key=lambda p: p.avg_rating, default=None)
    add("Гравець сезону", "🏅", mvp, f"оцінка {mvp.avg_rating}" if mvp else "")
    young = max((p for p in reg if p.age <= 21), key=lambda p: p.avg_rating, default=None)
    add("Найкращий молодий", "🌱", young, f"{young.age} р., оцінка {young.avg_rating}" if young else "")
    gk = max((p for p in reg if p.pos == "GK"), key=lambda p: p.avg_rating, default=None)
    add("Найкращий воротар", "🧤", gk, f"оцінка {gk.avg_rating}" if gk else "")
    playm = max(league, key=lambda p: (p.assists, p.goals), default=None)
    add("Король асистів", "🎯", playm if playm and playm.assists else None, f"{playm.assists} пас." if playm else "")
    mine = [p for p in w.squad(w.club_id) if p.apps >= 5]
    own = max(mine, key=lambda p: p.avg_rating, default=None)
    add("Гравець сезону клубу", "⭐", own, f"оцінка {own.avg_rating}" if own else "")
    entry = {"season": f"{2025 + w.season}/{str(2026 + w.season)[-2:]}", "items": items}
    w.awards.insert(0, entry)
    del w.awards[10:]
    return entry


# ---------------------------------------------------------------- dilemmas
def maybe_dilemma(w: World, rng: random.Random) -> None:
    if w.dilemmas or rng.random() > 0.16:
        return
    squad = w.squad(w.club_id)
    if len(squad) < 14:
        return
    xi = set(w.last_xi or [])
    kinds = []
    bench_stars = [p for p in squad if p.id not in xi and p.skill >= sorted((x.skill for x in squad), reverse=True)[10]
                   and p.available and p.age >= 21]
    if bench_stars:
        kinds.append("playtime")
    top = sorted(squad, key=lambda p: -p.skill)[:4]
    if top:
        kinds.append("raise")
    if len(xi) >= 11:
        kinds.append("conflict")
    youth = [p for p in squad if p.age <= 19 and p.potential >= p.skill + 8]
    if youth:
        kinds.append("youth")
    if not kinds:
        return
    kind = rng.choice(kinds)
    did = w.new_id()
    if kind == "playtime":
        p = rng.choice(bench_stars)
        d = {"kind": kind, "pid": p.id, "title": f"{p.name} хоче грати",
             "text": f"{p.name} ({p.skill}) незадоволений роллю запасного і прийшов до тебе в кабінет.",
             "options": [["promise", "Пообіцяти місце в основі"], ["sell", "Виставити на трансфер"],
                         ["fight", "Нехай доводить на тренуваннях"]]}
    elif kind == "raise":
        p = rng.choice(top)
        new = int(p.wage * 1.3 / 50) * 50
        d = {"kind": kind, "pid": p.id, "amount": new, "title": f"Агент {p.name} просить підвищення",
             "text": f"Агент вимагає зарплату {new:,} € на тиждень замість {p.wage:,} €.".replace(",", " "),
             "options": [["accept", "Погодитися"], ["half", "Запропонувати половину"], ["refuse", "Відмовити"]]}
    elif kind == "conflict":
        a, b = rng.sample([w.players[i] for i in xi if i in w.players and w.players[i].club_id == w.club_id], 2)
        d = {"kind": kind, "pid": a.id, "pid2": b.id, "title": "Конфлікт у роздягальні",
             "text": f"{a.name} і {b.name} посварилися після тренування. Команда чекає на твою реакцію.",
             "options": [["a", f"Стати на бік {a.name.split()[-1]}"], ["fine", "Оштрафувати обох"],
                         ["talk", "Провести командну розмову"]]}
    else:
        p = rng.choice(youth)
        d = {"kind": kind, "pid": p.id, "title": "Тренер академії радить",
             "text": f"Тренер молоді вважає, що {p.name} ({p.age} р., потенціал {p.potential}) готовий до великого футболу.",
             "options": [["promote", "Дати шанс в основі"], ["train", "Індивідуальна програма розвитку"],
                         ["wait", "Ще рано"]]}
    d["id"] = did
    w.dilemmas.append(d)


def resolve_dilemma(w: World, did: int, opt: str, rng: random.Random | None = None) -> tuple[bool, str]:
    rng = rng or random.Random()
    d = next((x for x in w.dilemmas if x["id"] == did), None)
    if not d:
        return False, "Ситуація вже вирішилась."
    w.dilemmas = [x for x in w.dilemmas if x["id"] != did]
    p = w.players.get(d["pid"])
    if not p or p.club_id != w.club_id:
        return True, "Гравець уже не в клубі."
    squad = w.squad(w.club_id)
    k = d["kind"]
    if k == "playtime":
        if opt == "promise":
            p.morale = min(100, p.morale + 18)
            p.resting = False
            return True, f"{p.name} окрилений обіцянкою (+18 настрою). Тепер постав його в основу!"
        if opt == "sell":
            from .transfers import set_listing
            set_listing(w, p.id, p.value())
            return True, f"{p.name} виставлений на трансфер."
        p.morale = max(10, p.morale - 10)
        for x in squad:
            if x.id != p.id:
                x.morale = min(100, x.morale + 2)
        return True, f"Команда оцінила принциповість (+2), а {p.name} засмучений (−10)."
    if k == "raise":
        if opt == "accept":
            p.wage = d["amount"]
            p.morale = min(100, p.morale + 15)
            return True, f"{p.name} задоволений новим контрактом (+15 настрою)."
        if opt == "half":
            if rng.random() < 0.6:
                p.wage = int((p.wage + d["amount"]) / 2 / 50) * 50
                p.morale = min(100, p.morale + 6)
                return True, f"Компроміс! {p.name} погодився на {p.wage:,} €/тиж.".replace(",", " ")
            p.morale = max(10, p.morale - 12)
            return True, f"{p.name} відхилив компроміс і образився (−12 настрою)."
        p.morale = max(10, p.morale - 20)
        if rng.random() < 0.3:
            p.listed = True
            p.ask = p.value()
            return True, f"{p.name} в люті і просить продати його. Гравця виставлено на трансфер."
        return True, f"{p.name} розчарований (−20 настрою)."
    if k == "conflict":
        b = w.players.get(d.get("pid2"))
        if opt == "a":
            p.morale = min(100, p.morale + 8)
            if b:
                b.morale = max(10, b.morale - 15)
            return True, "Конфлікт вичерпано, але один із гравців затаїв образу."
        if opt == "fine":
            for x in (p, b):
                if x:
                    x.morale = max(10, x.morale - 6)
            w.confidence = min(100, w.confidence + 3)
            return True, "Дисципліна понад усе: правління схвалює (+3 довіри)."
        for x in squad:
            x.morale = min(100, x.morale + 3)
        return True, "Командна розмова допомогла: +3 настрою всім."
    if k == "youth":
        if opt == "promote":
            p.morale = min(100, p.morale + 20)
            p.skill = min(p.potential, p.skill + 1)
            p.resting = False
            return True, f"{p.name} в захваті (+20 настрою, +1 майстерності). Знайди йому місце в складі!"
        if opt == "train":
            p.potential = min(96, p.potential + 2)
            return True, f"Програма розвитку: потенціал {p.name} зріс до {p.potential}."
        p.morale = max(10, p.morale - 5)
        return True, f"{p.name} продовжить у молодіжці."
    return True, "Готово."
