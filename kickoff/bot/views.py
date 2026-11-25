"""Text renderers and inline keyboards (Ukrainian UI)."""
from __future__ import annotations

from html import escape

from aiogram.types import InlineKeyboardButton as B
from aiogram.types import InlineKeyboardMarkup

from ..game.match import pick_lineup
from ..game.models import FORMATIONS, POS_UA, STYLES, TRAINING, World
from ..game.names import FLAGS
from ..game.season import (fair_ticket, next_fixture, position, sponsor_income, table, wage_bill)
from ..game.transfers import asking_price, money, upgrade_cost, wage_demand

DIV_NAME = {1: "Прем’єр-ліга", 2: "Перша ліга"}
PAGE = 8


def kb(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[B(text=t, callback_data=d) for t, d in row] for row in rows if row])


def back(to: str = "m", label: str = "⬅️ Назад") -> list:
    return [(label, to)]


def club_label(world: World, cid: int) -> str:
    c = world.clubs[cid]
    return f"{c.emoji} {escape(c.name)}"


def stars(skill: int) -> str:
    n = max(1, min(5, (skill - 35) // 10))
    return "★" * n + "☆" * (5 - n)


def fitness_icon(f: int) -> str:
    return "🟢" if f >= 85 else ("🟡" if f >= 65 else "🔴")


def morale_icon(m: int) -> str:
    return "😃" if m >= 80 else ("🙂" if m >= 55 else ("😐" if m >= 35 else "😠"))


def player_status(p) -> str:
    s = ""
    if p.injured:
        s += f" 🤕{p.injured}"
    if p.suspended:
        s += " 🟥"
    if p.listed:
        s += " 🏷"
    if p.resting:
        s += " 💤"
    if p.contract <= 1:
        s += " 📝"
    return s


def player_line(p, show_value: bool = False) -> str:
    line = (f"{POS_UA[p.pos]} <b>{p.skill}</b>/{p.potential} {escape(p.name)} {FLAGS.get(p.nation, '')}"
            f" {p.age}р {fitness_icon(p.fitness)}{player_status(p)}")
    if show_value:
        line += f" · {money(p.value())}"
    return line


# ------------------------------------------------------------------ main
def main_menu(world: World) -> tuple[str, InlineKeyboardMarkup]:
    c = world.club
    pos = position(world, c.id)
    nf = next_fixture(world)
    nxt = ""
    if nf:
        h, a = nf
        opp = a if h == c.id else h
        nxt = f"\n⏭ Наступний: {club_label(world, opp)} ({'вдома' if h == c.id else 'на виїзді'})"
    conf_bar = "🟩" * (world.confidence // 20) + "⬜" * (5 - world.confidence // 20)
    window = "🟢 відкрите" if world.transfer_window_open() else "🔴 закрите"
    text = (
        f"{c.emoji} <b>{escape(c.name)}</b> · {escape(c.city)}\n"
        f"🏆 {DIV_NAME[c.division]} · сезон {world.season}, тур {world.round}/{world.rounds_total}\n"
        f"📊 Місце: <b>{pos}</b> (ціль: топ-{world.board_target})\n"
        f"💰 Бюджет: <b>{money(c.budget)}</b> · ⭐ Репутація {c.reputation}\n"
        f"🤝 Довіра правління: {conf_bar} {world.confidence}%\n"
        f"🔁 Трансферне вікно: {window}"
        f"{nxt}"
    )
    offers = f" ({len(world.offers)})" if world.offers else ""
    rows = [
        [("⚽ Наступний матч", "nx")],
        [("👥 Склад", "sq:0"), ("🧠 Тактика", "tac")],
        [("📊 Таблиця", f"tb:{c.division}"), ("📅 Календар", "fx")],
        [("🔁 Трансфери", "tr"), (f"📨 Пропозиції{offers}", "of")],
        [("🏋️ Тренування", "trn"), ("🏦 Фінанси", "fin")],
        [("📰 Новини", "news"), ("🏛 Клуб і кар’єра", "club")],
    ]
    return text, kb(rows)


# ------------------------------------------------------------------ squad
def squad_view(world: World, page: int) -> tuple[str, InlineKeyboardMarkup]:
    order = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
    sq = sorted(world.squad(world.club_id), key=lambda p: (order[p.pos], -p.skill))
    pages = max(1, (len(sq) + PAGE - 1) // PAGE)
    page = max(0, min(page, pages - 1))
    chunk = sq[page * PAGE:(page + 1) * PAGE]
    avg = sum(p.skill for p in sq) / max(1, len(sq))
    text = (f"👥 <b>Склад</b> · гравців: {len(sq)}, середній рівень {avg:.1f}\n"
            f"Позначки: 🟢🟡🔴 форма, 🤕 травма, 🟥 дискваліфікація, 🏷 на продаж, 💤 відпочинок, 📝 контракт закінчується\n\n")
    text += "\n".join(player_line(p) for p in chunk)
    rows = [[(f"{POS_UA[p.pos]} {p.skill} {p.name}", f"pl:{p.id}")] for p in chunk]
    nav = []
    if page > 0:
        nav.append(("◀️", f"sq:{page - 1}"))
    nav.append((f"{page + 1}/{pages}", "noop"))
    if page < pages - 1:
        nav.append(("▶️", f"sq:{page + 1}"))
    rows.append(nav)
    rows.append([("📋 Стартовий склад", "xi"), ("⬅️ Меню", "m")])
    return text, kb(rows)


def player_card(world: World, pid: int, mine: bool) -> tuple[str, InlineKeyboardMarkup]:
    p = world.players[pid]
    club = club_label(world, p.club_id) if p.club_id else "Вільний агент"
    text = (
        f"{FLAGS.get(p.nation, '')} <b>{escape(p.name)}</b>\n"
        f"{POS_UA[p.pos]} · {p.age} років · {club}\n\n"
        f"Майстерність: <b>{p.skill}</b> {stars(p.skill)}\n"
        f"Потенціал: {p.potential} {stars(p.potential)}\n"
        f"Фізична форма: {fitness_icon(p.fitness)} {p.fitness}%\n"
        f"Настрій: {morale_icon(p.morale)} {p.morale}\n\n"
        f"Сезон: {p.apps} матчів, {p.goals} голів, {p.assists} передач, оцінка {p.avg_rating or '-'}\n"
        f"Кар’єра: {p.career_apps} матчів, {p.career_goals} голів\n\n"
        f"💶 Вартість: {money(p.value())}\n"
        f"💵 Зарплата: {money(p.wage)}/тиж · контракт ще {p.contract} сез.\n"
    )
    if p.injured:
        text += f"🤕 Травма: ще {p.injured} тур(и)\n"
    if p.suspended:
        text += f"🟥 Дискваліфікація: {p.suspended} матч(і)\n"
    rows = []
    if mine:
        rows.append([("💤 Не ставити" if not p.resting else "✅ Повернути в склад", f"pa:rest:{pid}"),
                     ("🏷 Зняти з продажу" if p.listed else "🏷 На продаж", f"pa:list:{pid}")])
        rows.append([("📝 Продовжити контракт", f"pa:renew:{pid}"), ("⚡ Швидкий продаж", f"pa:qs:{pid}")])
        rows.append([("📤 Розірвати контракт", f"pa:rel:{pid}")])
        rows.append(back("sq:0", "⬅️ До складу"))
    else:
        if p.club_id is None:
            text += f"\nБонус за підпис: {money(wage_demand(world, pid) * 4)}, зарплата {money(wage_demand(world, pid))}/тиж"
            rows.append([("✍️ Підписати", f"buy:{pid}")])
        else:
            text += f"\nЦіна клубу: <b>{money(asking_price(world, pid))}</b>, зарплата {money(wage_demand(world, pid))}/тиж"
            rows.append([(f"💰 Купити за {money(asking_price(world, pid))}", f"buy:{pid}")])
        rows.append(back(f"mk:{p.pos}:0", "⬅️ До ринку"))
    return text, kb(rows)


def lineup_view(world: World) -> tuple[str, InlineKeyboardMarkup]:
    lu = pick_lineup(world, world.club)
    lines = [f"📋 <b>Стартовий склад</b> ({world.club.formation}, {STYLES[world.club.style].lower()})\n"]
    for slot, p in lu:
        mark = "" if slot == p.pos else " ⚠️не на позиції"
        lines.append(f"{POS_UA[slot]} {p.skill} {escape(p.name)} {fitness_icon(p.fitness)}{mark}")
    lines.append("\nСклад обирається автоматично з найкращих доступних. "
                 "Щоб когось не ставити, відкрий картку гравця і натисни 💤.")
    return "\n".join(lines), kb([[("🧠 Тактика", "tac"), ("👥 Склад", "sq:0")], back()])


# ------------------------------------------------------------------ tactics/training
def tactics_view(world: World) -> tuple[str, InlineKeyboardMarkup]:
    c = world.club
    text = (f"🧠 <b>Тактика</b>\nСхема: <b>{c.formation}</b>\nСтиль: <b>{STYLES[c.style]}</b>\n\n"
            "• Атакувальний: більше моментів, але слабша оборона, гравці більше втомлюються\n"
            "• Оборонний: надійніше позаду, менше гостроти\n"
            "• Контратаки: віддаєш м’яч, але б’єш швидко\n"
            "• Пресинг: перевага в центрі поля, але сильна втома")
    f_rows, row = [], []
    for f in FORMATIONS:
        row.append((("✅ " if f == c.formation else "") + f, f"tf:{f}"))
        if len(row) == 4:
            f_rows.append(row)
            row = []
    if row:
        f_rows.append(row)
    s_rows = [[(("✅ " if s == c.style else "") + name, f"ts:{s}")] for s, name in STYLES.items()]
    return text, kb(f_rows + s_rows + [[("📋 Хто зіграє", "xi")], back()])


def training_view(world: World) -> tuple[str, InlineKeyboardMarkup]:
    text = (f"🏋️ <b>Тренування</b>\nФокус: <b>{TRAINING[world.training]}</b>\n"
            f"Рівень бази: {world.club.training_level}/5\n\n"
            "• Атака: швидший розвиток півзахисників і нападників\n"
            "• Оборона: швидший розвиток захисників і воротарів\n"
            "• Фізпідготовка: краще відновлення між матчами\n"
            "• Розвиток молоді: гравці до 21 року ростуть значно швидше")
    rows = [[(("✅ " if k == world.training else "") + v, f"tt:{k}")] for k, v in TRAINING.items()]
    return text, kb(rows + [back()])


# ------------------------------------------------------------------ table / fixtures
def table_view(world: World, div: int) -> tuple[str, InlineKeyboardMarkup]:
    rows = table(world, div)
    lines = [f"📊 <b>{DIV_NAME[div]}</b> · сезон {world.season}\n<code># Клуб            І  РМ  О</code>"]
    n = len(rows)
    for i, r in enumerate(rows, 1):
        c = world.clubs[r["club"]]
        name = c.name[:14].ljust(14)
        gd = r["gf"] - r["ga"]
        mark = ""
        if div == 1 and i > n - 2:
            mark = "🔻"
        elif div == 2 and i <= 2:
            mark = "🔺"
        elif i == 1:
            mark = "👑"
        line = f"<code>{i:>2} {name} {r['p']:>2} {gd:>+3} {r['pts']:>2}</code>{mark}"
        if c.is_user:
            line = f"<b>{line}</b> ⬅️"
        lines.append(line)
    other = 2 if div == 1 else 1
    return "\n".join(lines), kb([[(f"➡️ {DIV_NAME[other]}", f"tb:{other}"), ("🥇 Бомбардири", f"sc:{div}")],
                                  back()])


def scorers_view(world: World, div: int) -> tuple[str, InlineKeyboardMarkup]:
    ps = [p for p in world.players.values() if p.club_id and world.clubs[p.club_id].division == div and p.goals]
    ps.sort(key=lambda p: (p.goals, p.assists), reverse=True)
    lines = [f"🥇 <b>Бомбардири · {DIV_NAME[div]}</b>\n"]
    for i, p in enumerate(ps[:15], 1):
        lines.append(f"{i}. {escape(p.name)} ({club_label(world, p.club_id)}) · ⚽ {p.goals} · 🅰️ {p.assists}")
    if len(lines) == 1:
        lines.append("Ще ніхто не забивав.")
    return "\n".join(lines), kb([back(f"tb:{div}")])


def fixtures_view(world: World) -> tuple[str, InlineKeyboardMarkup]:
    div = world.club.division
    rounds = world.fixtures[div]
    res = {(r.round, r.home, r.away): r for r in world.results if r.division == div}
    lines = [f"📅 <b>Календар · сезон {world.season}</b>\n"]
    start = max(0, world.round - 4)
    for i in range(start, min(len(rounds), start + 12)):
        for h, a in rounds[i]:
            if world.club_id not in (h, a):
                continue
            opp = a if h == world.club_id else h
            where = "🏠" if h == world.club_id else "✈️"
            r = res.get((i, h, a))
            if r:
                gf, ga = (r.hg, r.ag) if h == world.club_id else (r.ag, r.hg)
                icon = "✅" if gf > ga else ("➖" if gf == ga else "❌")
                lines.append(f"Т{i + 1} {where} {club_label(world, opp)} {icon} {gf}:{ga}")
            else:
                lines.append(f"Т{i + 1} {where} {club_label(world, opp)}")
    return "\n".join(lines), kb([back()])


# ------------------------------------------------------------------ match
def preview_view(world: World) -> tuple[str, InlineKeyboardMarkup]:
    nf = next_fixture(world)
    if not nf:
        return "Сезон завершено.", kb([[("🏁 Підсумки сезону", "endseason")]])
    h, a = nf
    opp = world.clubs[a if h == world.club_id else h]

    def strength(cid):
        lu = pick_lineup(world, world.clubs[cid])
        return sum(p.skill for _, p in lu) / max(1, len(lu))

    my_s, op_s = strength(world.club_id), strength(opp.id)
    tbl = table(world, world.club.division)
    opp_row = next(r for r in tbl if r["club"] == opp.id)
    opp_pos = tbl.index(opp_row) + 1
    form = "".join({"W": "✅", "D": "➖", "L": "❌"}[x] for x in opp_row["form"][-5:]) or "-"
    unavailable = [p for p in world.squad(world.club_id) if not p.available]
    text = (f"⚽ <b>Тур {world.round + 1}</b>\n"
            f"{club_label(world, h)} — {club_label(world, a)}\n\n"
            f"Суперник: {opp_pos}-е місце, форма {form}\n"
            f"Схема суперника: {opp.formation}, {STYLES[opp.style].lower()}\n"
            f"Сила складу: ми <b>{my_s:.1f}</b> · вони <b>{op_s:.1f}</b>\n"
            f"Наша тактика: {world.club.formation}, {STYLES[world.club.style].lower()}")
    if unavailable:
        text += "\n\nНе зіграють: " + ", ".join(f"{escape(p.name)}{player_status(p)}" for p in unavailable[:6])
    rows = [[("▶️ Грати матч (трансляція)", "play:live")], [("⏩ Швидкий результат", "play:fast")],
            [("🧠 Тактика", "tac"), ("📋 Склад", "xi")], back()]
    return text, kb(rows)


EVENT_ICON = {"goal": "⚽", "yellow": "🟨", "red": "🟥", "injury": "🤕", "sub": "🔄", "save": "🧤", "miss": "💨"}


def event_line(world: World, e: dict, res: dict) -> str:
    side_club = world.clubs[res["home"] if e["side"] == 0 else res["away"]]
    pl = world.players.get(e.get("player")) if e.get("player") else None
    name = escape(pl.name) if pl else "гравець"
    t = e["type"]
    if t == "goal":
        a = world.players.get(e["assist"]) if e.get("assist") else None
        s = f"{e['min']}' ⚽ <b>ГОЛ!</b> {name} ({escape(side_club.name)})"
        if a:
            s += f", пас {escape(a.name)}"
        return s + f" · <b>{e['score'][0]}:{e['score'][1]}</b>"
    if t == "yellow":
        return f"{e['min']}' 🟨 {name} ({escape(side_club.name)})"
    if t == "red":
        return f"{e['min']}' 🟥 {name} вилучений{' (друга жовта)' if e.get('second') else ''}!"
    if t == "injury":
        return f"{e['min']}' 🤕 {name} травмувався (≈{e['weeks']} тур.)"
    if t == "sub":
        o, i = world.players.get(e["out"]), world.players.get(e["in"])
        if o and i:
            return f"{e['min']}' 🔄 {escape(i.name)} замість {escape(o.name)} ({escape(side_club.name)})"
        return ""
    if t == "save":
        gk = world.players.get(e.get("gk")) if e.get("gk") else None
        return f"{e['min']}' 🧤 Сейв! {escape(gk.name) if gk else 'Воротар'} відбиває удар, бив {name}"
    if t == "miss":
        return f"{e['min']}' 💨 Небезпечно! {name} б’є повз ворота"
    return ""


def live_text(world: World, res: dict, upto: int) -> str:
    hg = sum(1 for e in res["events"] if e["type"] == "goal" and e["side"] == 0 and e["min"] <= upto)
    ag = sum(1 for e in res["events"] if e["type"] == "goal" and e["side"] == 1 and e["min"] <= upto)
    head = (f"{club_label(world, res['home'])} <b>{hg}:{ag}</b> {club_label(world, res['away'])}\n"
            f"⏱ {'Кінець матчу' if upto >= 90 else ('Перерва' if upto == 45 else f'{upto} хв')}\n\n")
    lines = [event_line(world, e, res) for e in res["events"] if e["min"] <= upto]
    lines = [x for x in lines if x]
    if len(lines) > 18:
        lines = ["…"] + lines[-18:]
    return head + ("\n".join(lines) if lines else "Гра триває…")


def report_text(world: World, res: dict) -> str:
    text = live_text(world, res, 90)
    poss = res["possession"]
    text += (f"\n\n📈 <b>Статистика</b>\nВолодіння: {poss}% — {100 - poss}%\n"
             f"Удари: {res['shots'][0]} — {res['shots'][1]}\n"
             f"У площину: {res['on_target'][0]} — {res['on_target'][1]}\n"
             f"xG: {res['xg'][0]} — {res['xg'][1]}\n"
             f"Глядачів: {res.get('attendance', 0):,}".replace(",", " "))
    motm = world.players.get(int(res["motm"])) if res.get("motm") else None
    if motm:
        text += f"\n🌟 Гравець матчу: {escape(motm.name)} ({res['ratings'].get(res['motm'], res['ratings'].get(str(res['motm'])))})"
    mine = [(world.players.get(int(pid)), r) for pid, r in res["ratings"].items()
            if world.players.get(int(pid)) and world.players[int(pid)].club_id == world.club_id]
    mine.sort(key=lambda x: x[1], reverse=True)
    if mine:
        text += "\n\n<b>Оцінки наших:</b>\n" + "\n".join(f"{r} {escape(p.name)}" for p, r in mine[:11])
    return text


def after_match_kb() -> InlineKeyboardMarkup:
    return kb([[("⚽ Далі", "nx"), ("📊 Таблиця", "tbm")], [("🏠 Меню", "m")]])


# ------------------------------------------------------------------ transfers
def transfers_view(world: World) -> tuple[str, InlineKeyboardMarkup]:
    window = "🟢 Вікно відкрите" if world.transfer_window_open() else "🔴 Вікно закрите (можна підписати лише вільних агентів)"
    text = (f"🔁 <b>Трансферний ринок</b>\n{window}\nБюджет: <b>{money(world.club.budget)}</b>\n"
            f"Гравців у складі: {len(world.squad(world.club_id))}/30\n\nОбери позицію:")
    rows = [[("🧤 Воротарі", "mk:GK:0"), ("🛡 Захисники", "mk:DF:0")],
            [("🎯 Півзахисники", "mk:MF:0"), ("⚡ Нападники", "mk:FW:0")],
            [("🆓 Вільні агенти", "mk:FA:0"), ("🌟 Молоді таланти", "mk:YT:0")],
            back()]
    return text, kb(rows)


def market_list(world: World, key: str) -> list:
    others = [p for p in world.players.values() if p.club_id != world.club_id]
    if key == "FA":
        ps = [p for p in others if p.club_id is None]
    elif key == "YT":
        ps = [p for p in others if p.age <= 21 and p.potential >= 70]
        ps.sort(key=lambda p: p.potential, reverse=True)
        return ps
    else:
        ps = [p for p in others if p.pos == key]
    ps.sort(key=lambda p: (p.skill, p.potential), reverse=True)
    return ps


def market_view(world: World, key: str, page: int) -> tuple[str, InlineKeyboardMarkup]:
    ps = market_list(world, key)
    pages = max(1, (len(ps) + PAGE - 1) // PAGE)
    page = max(0, min(page, pages - 1))
    chunk = ps[page * PAGE:(page + 1) * PAGE]
    title = {"GK": "Воротарі", "DF": "Захисники", "MF": "Півзахисники", "FW": "Нападники",
             "FA": "Вільні агенти", "YT": "Молоді таланти"}[key]
    text = f"🔎 <b>{title}</b> · бюджет {money(world.club.budget)}\n\n"
    lines = []
    for p in chunk:
        price = "вільний" if p.club_id is None else money(asking_price(world, p.id))
        where = f" · {escape(world.clubs[p.club_id].name)}" if p.club_id else ""
        lines.append(f"{player_line(p)}{where} · {price}")
    text += "\n".join(lines) or "Нікого немає."
    rows = [[(f"{POS_UA[p.pos]} {p.skill}/{p.potential} {p.name}", f"mp:{p.id}")] for p in chunk]
    nav = []
    if page > 0:
        nav.append(("◀️", f"mk:{key}:{page - 1}"))
    nav.append((f"{page + 1}/{pages}", "noop"))
    if page < pages - 1:
        nav.append(("▶️", f"mk:{key}:{page + 1}"))
    rows.append(nav)
    rows.append(back("tr"))
    return text, kb(rows)


def offers_view(world: World) -> tuple[str, InlineKeyboardMarkup]:
    if not world.offers:
        return ("📨 Пропозицій немає.\n\nВистав гравця на продаж (🏷 у картці гравця), "
                "і клуби почнуть робити ставки під час трансферного вікна."), kb([back()])
    lines = ["📨 <b>Пропозиції за твоїх гравців</b> (діють до наступного туру)\n"]
    rows = []
    for o in world.offers:
        p = world.players.get(o.player_id)
        if not p:
            continue
        lines.append(f"{club_label(world, o.club_id)} хоче {escape(p.name)} ({p.skill}) за <b>{money(o.fee)}</b> "
                     f"(вартість {money(p.value())})")
        rows.append([(f"✅ {p.name.split()[-1]} {money(o.fee)}", f"oa:{o.id}"), ("❌", f"or:{o.id}")])
    return "\n".join(lines), kb(rows + [back()])


# ------------------------------------------------------------------ finance / club
def finance_view(world: World) -> tuple[str, InlineKeyboardMarkup]:
    c = world.club
    f = world.season_finances
    wages = wage_bill(world, c.id)
    text = (f"🏦 <b>Фінанси</b>\nБюджет: <b>{money(c.budget)}</b>\n\n"
            f"Зарплати: {money(wages)}/тиж\nСпонсори: {money(sponsor_income(c))}/тиж\n"
            f"🏟 Стадіон: {c.stadium:,} місць · квиток €{c.ticket_price} (рекомендовано €{fair_ticket(c)})\n\n"
            f"<b>Цей сезон</b>\nДоходи: {money(f['income'])}\nЗарплати: {money(f['wages'])}\n"
            f"Продажі: {money(f['transfers_in'])}\nВитрати на трансфери й інфраструктуру: {money(f['transfers_out'])}\n\n"
            f"<b>Інфраструктура</b>\n🏋️ Тренувальна база: {c.training_level}/5\n🎓 Академія: {c.academy_level}/5"
            ).replace(",", " ")
    rows = [[("🎟 −1€", "tp:-"), (f"Квиток €{c.ticket_price}", "noop"), ("🎟 +1€", "tp:+")]]
    for kind, label in (("stadium", "🏟 +2500 місць"), ("training", "🏋️ База"), ("academy", "🎓 Академія")):
        cost = upgrade_cost(world, kind)
        if cost:
            rows.append([(f"{label} · {money(cost)}", f"up:{kind}")])
    rows.append(back())
    return text, kb(rows)


def club_view(world: World) -> tuple[str, InlineKeyboardMarkup]:
    hist = "\n".join(f"С{h['season']}: {escape(world.clubs[h['club']].name)}, {DIV_NAME[h['division']]}, "
                     f"{h['pos']}-е (ціль {h['target']})" for h in world.history[-8:]) or "Поки немає завершених сезонів."
    troph = "\n".join(world.trophies) or "Поки без трофеїв. Все попереду!"
    text = (f"🏛 <b>Кар’єра тренера {escape(world.manager)}</b>\n\n<b>Трофеї</b>\n{troph}\n\n"
            f"<b>Історія</b>\n{hist}")
    return text, kb([[("🏅 Зала слави", "hall")], [("🔄 Почати нову кар’єру", "newask")], back()])


def news_view(world: World) -> tuple[str, InlineKeyboardMarkup]:
    text = "📰 <b>Новини</b>\n\n" + ("\n".join(escape(n) for n in world.news[:15]) or "Тиша.")
    return text, kb([back()])


def choose_division_view() -> tuple[str, InlineKeyboardMarkup]:
    text = ("🏟 <b>Обери, з чого почати</b>\n\n"
            "🔝 <b>Прем’єр-ліга</b>: сильні клуби, великі гроші й великі очікування.\n"
            "⬆️ <b>Перша ліга</b>: скромний бюджет, але шлях від низів до чемпіонства. Справжній виклик!")
    return text, kb([[("🔝 Прем’єр-ліга", "pick:1")], [("⬆️ Перша ліга", "pick:2")]])


def choose_club_view(world: World, div: int) -> tuple[str, InlineKeyboardMarkup]:
    clubs = sorted(world.division_clubs(div), key=lambda c: c.reputation, reverse=True)
    lines = [f"Обери клуб · {DIV_NAME[div]}\n"]
    rows = []
    for c in clubs:
        sq = world.squad(c.id)
        avg = sum(p.skill for p in sq) / max(1, len(sq))
        lines.append(f"{c.emoji} <b>{escape(c.name)}</b> ({escape(c.city)}) · ⭐{c.reputation} · сила {avg:.0f} · {money(c.budget)}")
        rows.append([(f"{c.emoji} {c.name} ⭐{c.reputation}", f"cc:{c.id}")])
    rows.append([("⬅️ Назад", "pickdiv")])
    return "\n".join(lines), kb(rows)


def season_summary_text(world: World, s: dict) -> str:
    div = s["division"]
    lines = [f"🏁 <b>Сезон {s['season']} завершено!</b>\n",
             f"Твій результат: <b>{s['position']}-е місце</b> у {DIV_NAME[div]} (ціль: топ-{s['target']})"]
    if s.get("prize"):
        lines.append(f"💰 Призові: {money(s['prize'])}")
    for d, info in sorted(s["divisions"].items()):
        lines.append(f"\n<b>{DIV_NAME[int(d)]}</b>")
        lines.append(f"👑 Чемпіон: {club_label(world, info['champion'])}")
        if info.get("top_scorer"):
            pid, g = info["top_scorer"]
            p = world.players.get(pid)
            if p:
                lines.append(f"🥇 Бомбардир: {escape(p.name)} ({g})")
        if info.get("best_player"):
            pid, r = info["best_player"]
            p = world.players.get(pid)
            if p:
                lines.append(f"🌟 Найкращий гравець: {escape(p.name)} ({r})")
    if s.get("promoted"):
        lines.append("\n🔺 Підвищились: " + ", ".join(club_label(world, c) for c in s["promoted"]))
        lines.append("🔻 Вибули: " + ", ".join(club_label(world, c) for c in s["relegated"]))
    if s.get("retired"):
        lines.append("\n👋 Завершили кар’єру: " + ", ".join(escape(n) for n in s["retired"]))
    if s.get("left"):
        lines.append("📝 Пішли після закінчення контракту: " + ", ".join(escape(n) for n in s["left"]))
    if s.get("youth"):
        names = [world.players[i] for i in s["youth"] if i in world.players]
        lines.append("🎓 З академії: " + ", ".join(f"{escape(p.name)} ({POS_UA[p.pos]}, {p.skill}/{p.potential})" for p in names))
    if s.get("emergency"):
        lines.append("🚑 Правління терміново дозаявило: " + ", ".join(escape(n) for n in s["emergency"]))
    lines.append(f"\n🤝 Довіра правління: {world.confidence}%")
    if not world.fired:
        lines.append(f"Нова ціль на сезон {world.season}: топ-{world.board_target}")
    return "\n".join(lines)
