"""Rich chat messages: welcome card, season report, level-ups. Pure text builders (HTML parse mode)."""
from __future__ import annotations

from html import escape

from ..game.leagues import LEAGUES
from ..meta import RANKS, Profile


def money(v: int) -> str:
    s = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000:
        return f"{s}€{v / 1_000_000:.1f}M"
    if v >= 1000:
        return f"{s}€{v // 1000}K"
    return f"{s}€{v}"


def bar(cur: int, total: int, width: int = 10, full: str = "▰", empty: str = "▱") -> str:
    n = 0 if total <= 0 else max(0, min(width, round(cur / total * width)))
    return full * n + empty * (width - n)


def level_block(p: Profile) -> str:
    title, level, xp_in, xp_need = p.rank
    nxt = RANKS[level][1] if level < len(RANKS) else None
    line = f"⭐ <b>Рівень {level} · {escape(title)}</b>\n<code>{bar(xp_in, xp_need)}</code> {xp_in}/{xp_need} XP"
    if nxt:
        line += f"\n<i>до рангу «{escape(nxt)}»: {xp_need - xp_in} XP</i>"
    return line


def welcome(p: Profile, career: dict | None) -> str:
    lines = [
        "🏟 <b>KICKOFF · Футбольний менеджер</b>",
        "",
        "Очоль справжній клуб і пройди шлях від Першої ліги до чемпіонства.",
        "⚽ Матчі наживо · 🔁 Трансфери · 🧠 Тактика · 🎓 Академія",
        "🇺🇦 УПЛ · 🏴󠁧󠁢󠁥󠁮󠁧󠁿 АПЛ · 🇪🇸 Ла Ліга · 🇩🇪 Бундесліга · 🇮🇹 Серія А · 🇫🇷 Ліга 1",
        "",
        f"👤 <b>{escape(p.name)}</b>",
        level_block(p),
        f"🪙 Монети: <b>{p.coins}</b>",
    ]
    if career:
        lines += ["", f"📍 <b>{escape(career['club'])}</b> · {escape(career['league'])} · сезон {career['season']}",
                  f"📊 {career['position']} місце з {career['of']} · {career['points']} очок"]
    if p.daily_available():
        lines += ["", f"🎁 Щоденний бонус чекає: <b>+{p.daily_amount()}</b> монет"]
    lines += ["", "Тисни <b>«Грати»</b> 👇"]
    return "\n".join(lines)


def season_report(s: dict, p: Profile, level_before: int) -> str:
    pos, target = s["position"], s["target"]
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, "🎖")
    league = LEAGUES[s["division"]]["short"]
    lines = [f"🏁 <b>Сезон {s['season_label']} завершено!</b>", "",
             f"🏟 <b>{escape(s['club'])}</b> · {escape(league)}",
             f"📊 Позиція: <b>{pos} місце</b> {medal}",
             f"📈 {s['pts']} очок · {s['w']}В-{s['d']}Н-{s['l']}П · голи {s['gf']}:{s['ga']}"]
    trophies = []
    if pos == 1:
        trophies.append(f"🏆 Чемпіон: {league}")
    if s.get("promoted_me"):
        trophies.append("🚀 Підвищення до УПЛ")
    for name in s.get("cups_won", []):
        trophies.append(f"{'⭐' if 'чемпіонів' in name else '🏆'} {name}")
    lines += ["", "🏆 <b>Трофеї сезону:</b>"] + ([f"   {t}" for t in trophies] or ["   цього разу без трофеїв"])
    if s.get("scorer"):
        lines += ["", f"⚽ Найкращий бомбардир: <b>{escape(s['scorer'][0])}</b> · {s['scorer'][1]} гол."]
    if s.get("best"):
        lines.append(f"🌟 Гравець сезону: <b>{escape(s['best'][0])}</b> · сер. оцінка {s['best'][1]}")
    if s.get("prize"):
        lines.append(f"💰 Призові: <b>{money(s['prize'])}</b>")
    lines.append("")
    if s.get("relegated_me"):
        lines.append("🔻 <b>Команда вилетіла.</b> Правління чекає негайного повернення.")
    elif pos <= target:
        lines.append(f"✅ <b>Правління задоволене:</b> ціль топ-{target} виконана.")
    else:
        lines.append(f"⚠️ <b>Правління розчароване:</b> ціль була топ-{target}.")
    lines.append(f"🤝 Довіра: <code>{bar(s['confidence'], 100)}</code> {s['confidence']}%")
    lines += ["", f"✨ +{s['xp']} XP за сезон"]
    if p.rank[1] > level_before:
        lines.append(f"🎉 <b>Новий рівень {p.rank[1]}!</b> Тепер ти «{escape(p.rank[0])}»")
    lines.append(level_block(p))
    if s.get("fired"):
        lines += ["", "🚪 <b>Тебе звільнили.</b> Почни нову кар’єру в іншому клубі!"]
    else:
        lines += ["", f"🎯 Нова ціль: <b>топ-{s['new_target']}</b>", "Новий сезон уже чекає, заходь і веди команду далі! ⚽"]
    return "\n".join(lines)


def level_up(p: Profile) -> str:
    title, level, _, _ = p.rank
    return (f"🎉 <b>Новий рівень тренера: {level}!</b>\nТепер ти «{escape(title)}».\n\n{level_block(p)}\n\n"
            "Продовжуй вигравати, щоб відкрити нові ранги 🏆")
