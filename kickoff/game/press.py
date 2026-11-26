"""Post-match press conference: a large pool of context-aware questions that rarely repeat."""
from __future__ import annotations

import random

# answer archetypes: effect + several phrasings (one is picked at random each time)
ANSWERS = {
    "humble": ({"morale": 2, "boost": 1.02}, ["Ми лише на початку шляху", "Рано робити висновки, сезон довгий",
                                             "Поважаємо кожного суперника, далі працюємо", "Ноги на землі, голова холодна"]),
    "hype": ({"morale": 5, "conf": 2, "boost": 0.99}, ["Нас уже ніхто не зупинить!", "Ми граємо за титул, і це не секрет",
                                                      "Хай усі бояться, ми тільки розганяємось", "Це лише трейлер того, що буде далі"]),
    "players": ({"morale": 6}, ["Це повністю заслуга хлопців", "Я просто пишаюся цією роздягальнею",
                                "Гравці віддали все до останньої краплі", "Аплодисменти команді, не мені"]),
    "tactics": ({"conf": 3}, ["Ми переграли їх тактично", "План на гру спрацював ідеально",
                              "Ми знайшли слабке місце в їхньому захисті", "Тиждень підготовки окупився"]),
    "spirit": ({"morale": 4}, ["Характер і самовіддача команди", "Ця команда ніколи не здається",
                               "Ми виграли серцем, а не ногами", "Дух у роздягальні неймовірний"]),
    "lucky": ({"boost": 1.02, "morale": -1}, ["Чесно, трохи пощастило", "Фортуна була на нашому боці",
                                              "Сьогодні нам допомогли штанги", "Треба визнати, суперник заслуговував більшого"]),
    "fans": ({"conf": 3, "morale": 2}, ["Ця перемога для наших фанатів", "Трибуни сьогодні грали за нас",
                                        "Дякую кожному, хто прийшов на стадіон", "Фанати наш дванадцятий гравець"]),
    "ok": ({"morale": 2}, ["Очко теж важливе", "Нічия на такому полі нормальний результат",
                           "Беремо очко і рухаємося далі", "Не програти теж уміння"]),
    "angry": ({"morale": -2, "boost": 1.03}, ["Ні, ми мали вигравати", "Я злий, і гравці теж мають бути злі",
                                              "Це два втрачені очки, не одне здобуте", "Такі матчі треба дотискати"]),
    "ref": ({"conf": -2, "morale": 3}, ["Суддя забрав у нас перемогу", "Подивіться повтор того епізоду, все зрозуміло",
                                        "Про суддівство краще промовчу", "VAR сьогодні, схоже, вимкнули"]),
    "blame": ({"morale": -5, "boost": 1.04}, ["Гравці не виконали установку", "Деякі хлопці сьогодні просто гуляли полем",
                                              "Так грати не можна, будуть висновки", "Я чекаю набагато більшого від лідерів"]),
    "me": ({"morale": 4, "conf": -2}, ["Відповідальність на мені", "Це моя помилка у виборі складу",
                                       "Я неправильно підготував команду", "Критикуйте мене, не гравців"]),
    "future": ({"morale": 1, "boost": 1.01}, ["Робимо висновки і йдемо далі", "Наступний матч уже завтра в голові",
                                              "Розберемо гру і виправимо помилки", "Поразка теж урок"]),
    "sorry": ({"conf": 2, "morale": -1}, ["Вибачаюсь перед фанатами", "Уболівальники заслуговують на краще",
                                          "Мені соромно за цю гру", "Ми підвели людей на трибунах"]),
    "fight": ({"boost": 1.05, "morale": -2}, ["Наступного матчу побачите іншу команду", "Ми повернемося злішими",
                                              "Це була остання така гра цього сезону", "Обіцяю реакцію вже в наступному турі"]),
    "excuse": ({"conf": -4, "morale": 3}, ["У нас купа травм і втома", "Графік матчів просто вбивчий",
                                           "Поле було в жахливому стані", "Нам не дали нормально відновитися"]),
    "praise_one": ({"morale": 3}, ["{star} сьогодні був неймовірний", "Окреме спасибі {star}, справжній лідер",
                                   "{star} показав, чому він у основі"]),
    "team_first": ({"morale": 2, "conf": 1}, ["Я не виділяю нікого, перемогла команда", "Футбол командна гра, усі молодці",
                                              "Індивідуальні оцінки залишу для роздягальні"]),
    "respect": ({"conf": 2}, ["{opp} дуже сильна команда, повага їм", "Велика повага суперникові і їхньому тренеру",
                              "{opp} змусили нас страждати"]),
    "provoke": ({"morale": 3, "boost": 1.03, "conf": -1}, ["{opp}? Чесно, я чекав від них більшого",
                                                           "Ми були на голову сильніші", "Нехай {opp} звикають програвати нам"]),
    "noanswer": ({}, ["Без коментарів", "Наступне питання, будь ласка", "Я вже все сказав"]),
    "board": ({"conf": 4, "morale": -1}, ["Довіряю керівництву, ми на одній хвилі", "Президент мене повністю підтримує",
                                          "Розмови про відставку не мої питання"]),
    "transfer_yes": ({"conf": 2, "morale": -2}, ["Так, нам потрібні підсилення", "Будемо активні на трансферному ринку",
                                                 "Позиції, які треба закрити, ми знаємо"]),
    "transfer_no": ({"morale": 3}, ["Я довіряю цій групі гравців", "Нікого не купуватимемо, у нас усе є",
                                    "Найкращий трансфер це розвиток своїх"]),
    "youth": ({"morale": 2, "conf": 1}, ["Молодь отримає шанс, обіцяю", "Наша академія це майбутнє клубу",
                                         "Двері основи відкриті для кожного юнака"]),
    "target_big": ({"conf": 3, "boost": 1.01}, ["Ціль одна: виграти все", "Мета: трофей до кінця сезону",
                                                "Ми тут не для участі, а для перемог"]),
    "target_calm": ({"morale": 2}, ["Йдемо крок за кроком", "Головне стабільність, решта прийде",
                                    "Таблицю подивимося в травні"]),
}

# question templates by situation; each lists answer archetypes (3 are shown)
Q = {
    "bigwin": [
        ("Розгромна перемога над {opp}! Тепер ви фаворити?", ["humble", "hype", "players", "target_big"]),
        ("{score}! Ви очікували такої переваги?", ["tactics", "humble", "provoke", "players"]),
        ("Ваша команда забила {gf}. Звідки така атакувальна міць?", ["tactics", "players", "spirit", "praise_one"]),
        ("Фанати вже співають про чемпіонство. Ваша реакція?", ["hype", "humble", "fans", "target_calm"]),
        ("{star} був у вогні. Він найкращий у лізі?", ["praise_one", "team_first", "hype"]),
        ("Тренер {opp} сказав, що ви просто грали проти змученої команди. Відповісте?", ["provoke", "respect", "noanswer", "tactics"]),
        ("Такий розгром ваша найкраща гра сезону?", ["players", "humble", "hype", "tactics"]),
        ("Що ви сказали гравцям після такого матчу?", ["players", "humble", "spirit", "fans"]),
    ],
    "win": [
        ("Важлива перемога. Що було ключовим?", ["tactics", "spirit", "lucky", "players"]),
        ("Перемога над {opp}. Чи була вона заслуженою?", ["tactics", "lucky", "respect", "spirit"]),
        ("{star} знову вирішив гру. Ви залежите від нього?", ["praise_one", "team_first", "players"]),
        ("Три очки в кишені. Куди тепер цілитесь?", ["target_big", "target_calm", "humble"]),
        ("Була напруга в кінці матчу. Нерви?", ["spirit", "lucky", "humble", "tactics"]),
        ("Кажуть, у вас найкраща форма за весь сезон. Згодні?", ["hype", "humble", "players"]),
        ("{opp} мали свої моменти. Не боялися втратити перемогу?", ["lucky", "spirit", "tactics", "respect"]),
        ("Чи потрібні команді підсилення, навіть коли ви перемагаєте?", ["transfer_yes", "transfer_no", "youth"]),
        ("Сьогодні грала молодь. Це новий курс?", ["youth", "team_first", "target_calm"]),
        ("Ваша зміна в другому таймі спрацювала. Геніальний хід?", ["tactics", "players", "humble"]),
        ("Що для вас важливіше: красива гра чи результат?", ["tactics", "target_big", "spirit"]),
    ],
    "draw": [
        ("Нічия. Ви задоволені результатом?", ["ok", "angry", "ref"]),
        ("Нічия з {opp}. Це втрачені очки?", ["angry", "ok", "respect", "future"]),
        ("Ваша команда не змогла забити більше. Проблема в атаці?", ["transfer_yes", "transfer_no", "blame", "future"]),
        ("Суддя скасував момент наприкінці. Ваша думка?", ["ref", "noanswer", "ok"]),
        ("{score}. Чи бракувало сміливості?", ["angry", "me", "tactics", "ok"]),
        ("Друга нічия поспіль?", ["future", "angry", "target_calm", "excuse"]),
        ("Чого не вистачило для перемоги?", ["angry", "excuse", "me", "future"]),
        ("Вболівальники свистіли в кінці. Чуєте їх?", ["sorry", "fans", "fight", "noanswer"]),
    ],
    "loss": [
        ("Поразка. Що пішло не так?", ["blame", "me", "future"]),
        ("Поразка від {opp}. Ви недооцінили суперника?", ["me", "respect", "excuse", "future"]),
        ("{score}. Ви чекали на такий результат?", ["blame", "future", "excuse", "fight"]),
        ("Ходять чутки, що правління незадоволене. Ваша посада під загрозою?", ["board", "noanswer", "fight"]),
        ("Захист сьогодні розвалився. Купуватимете нових гравців?", ["transfer_yes", "transfer_no", "blame"]),
        ("Ви довго не робили замін. Чому?", ["me", "excuse", "noanswer", "tactics"]),
        ("Хто персонально винен у цій поразці?", ["me", "blame", "team_first", "noanswer"]),
        ("{opp} святкують. Що скажете їм?", ["respect", "fight", "provoke", "noanswer"]),
        ("Ви ще вірите в свою ціль на сезон?", ["target_big", "target_calm", "fight"]),
        ("Що ви скажете фанатам, які їхали за вами на виїзд?", ["sorry", "fight", "fans"]),
    ],
    "bigloss": [
        ("Розгром… Уболівальники вимагають пояснень.", ["sorry", "fight", "excuse"]),
        ("{score}. Це найгірший матч вашої кар’єри?", ["me", "sorry", "fight", "noanswer"]),
        ("Після такого розгрому подасте у відставку?", ["board", "fight", "noanswer"]),
        ("Гравці взагалі слухають вашу установку?", ["blame", "me", "noanswer", "team_first"]),
        ("{opp} забили вам {ga}. Як це пояснити?", ["excuse", "me", "respect", "blame"]),
        ("Фанати скандували проти вас. Як реагуєте?", ["sorry", "fight", "board"]),
        ("Чи будуть жорсткі рішення в складі?", ["blame", "transfer_yes", "youth", "fight"]),
    ],
}


def _seen(w) -> list:
    return w.records.setdefault("_press_seen", [])


def open_press(w, res: dict, rng: random.Random | None = None) -> None:
    rng = rng or random.Random()
    home = res["home"] == w.club_id
    gf, ga = (res["hg"], res["ag"]) if home else (res["ag"], res["hg"])
    kind = "bigwin" if gf - ga >= 3 else "win" if gf > ga else "draw" if gf == ga else "bigloss" if ga - gf >= 3 else "loss"
    opp = w.clubs[res["away"] if home else res["home"]].name
    mine = {int(k): v for k, v in res.get("ratings", {}).items()}
    squad_ids = {p.id for p in w.squad(w.club_id)}
    best = max((pid for pid in mine if pid in squad_ids), key=lambda pid: mine[pid], default=None)
    star = w.players[best].name if best in w.players else "наш лідер"
    seen = _seen(w)
    pool = [(i, q) for i, q in enumerate(Q[kind]) if f"{kind}{i}" not in seen] or list(enumerate(Q[kind]))
    qi, (text, archs) = rng.choice(pool)
    seen.append(f"{kind}{qi}")
    del seen[:-30]
    fmt = {"opp": opp, "score": f"{gf}:{ga}", "gf": gf, "ga": ga, "star": star}
    picked = rng.sample(archs, min(3, len(archs)))
    answers = [{"id": a, "text": rng.choice(ANSWERS[a][1]).format(**fmt)} for a in picked]
    w.press = {"kind": kind, "q": text.format(**fmt), "answers": answers,
               "reporter": rng.choice(["Футбол 24", "UA-Футбол", "Спорт Арена", "Tribuna", "Goal Daily", "ТелеСпорт",
                                       "Sky Sports", "Marca", "Gazzetta", "L’Équipe", "Kicker", "The Athletic"])}


def answer_press(w, aid: str) -> tuple[bool, str]:
    if not w.press:
        return False, "Пресконференцію вже завершено."
    if aid not in {a["id"] for a in w.press["answers"]}:
        return False, "Невідома відповідь."
    eff = ANSWERS[aid][0]
    for p in w.squad(w.club_id):
        p.morale = max(10, min(100, p.morale + eff.get("morale", 0)))
    w.confidence = max(0, min(100, w.confidence + eff.get("conf", 0)))
    if eff.get("boost"):
        w.records["_boost"] = eff["boost"]
    parts = []
    if eff.get("morale"):
        parts.append(f"настрій {'+' if eff['morale'] > 0 else ''}{eff['morale']}")
    if eff.get("conf"):
        parts.append(f"довіра {'+' if eff['conf'] > 0 else ''}{eff['conf']}")
    if eff.get("boost", 1) > 1:
        parts.append("команда заведена на наступний матч")
    elif eff.get("boost", 1) < 1:
        parts.append("ризик недооцінити суперника")
    w.press = {}
    return True, "🎙 " + (", ".join(parts) or "журналісти задоволені")
