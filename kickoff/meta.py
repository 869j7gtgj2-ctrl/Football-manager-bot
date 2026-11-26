"""Meta progression shared by all careers of a user: coins, XP/rank, daily reward, tasks, slots, shop."""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field

MAX_SLOTS = 3
FREE_SLOTS = 2
SLOT_PRICE = {2: 100}

RANKS = [
    (0, "Новачок"),
    (100, "Асистент"),
    (300, "Тренер"),
    (700, "Досвідчений тренер"),
    (1500, "Топ-тренер"),
    (3000, "Легенда"),
]

DAILY_TASKS = {
    "play3": {"title": "Зіграй 3 матчі", "goal": 3, "reward": 10, "counter": "matches"},
    "win1": {"title": "Здобудь перемогу", "goal": 1, "reward": 10, "counter": "wins"},
    "clean1": {"title": "Зіграй на нуль", "goal": 1, "reward": 15, "counter": "clean"},
    "score3": {"title": "Забий 3+ голи в матчі", "goal": 1, "reward": 20, "counter": "big"},
}

ACHIEVEMENTS = {
    "first_win": {"title": "Перша перемога", "reward": 15},
    "first_season": {"title": "Завершити сезон", "reward": 30},
    "target_met": {"title": "Виконати ціль правління", "reward": 40},
    "promotion": {"title": "Вийти в Прем’єр-лігу", "reward": 60},
    "title": {"title": "Стати чемпіоном", "reward": 100},
    "unbeaten5": {"title": "5 матчів без поразок", "reward": 25},
}

# weekly challenges: 3 are picked per ISO week (same for every manager, so friends can race)
WEEKLY = {
    "w_wins": {"title": "Виграй 8 матчів", "goal": 8, "counter": "wins", "coins": 40},
    "w_goals": {"title": "Забий 25 голів", "goal": 25, "counter": "goals", "coins": 40},
    "w_clean": {"title": "Зіграй на нуль 4 рази", "goal": 4, "counter": "clean", "coins": 45},
    "w_big": {"title": "Розгроми суперника 3 рази (3+ голи різниці)", "goal": 3, "counter": "rout", "coins": 50},
    "w_unbeaten": {"title": "Серія 6 матчів без поразок", "goal": 6, "counter": "streak", "coins": 50},
    "w_matches": {"title": "Зіграй 15 матчів", "goal": 15, "counter": "matches", "coins": 30},
    "w_comeback": {"title": "Не програй, пропустивши першим, 2 рази", "goal": 2, "counter": "comeback", "coins": 55},
    "w_cup": {"title": "Виграй 2 кубкові або єврокубкові матчі", "goal": 2, "counter": "cupwins", "coins": 45},
}
WEEKLY_BONUS_GEMS = 10


def week_key() -> str:
    y, w, _ = dt.date.today().isocalendar()
    return f"{y}-W{w:02d}"


PREMIUM = {
    "slot": {"title": "Додатковий слот кар’єри", "desc": "Ще одна паралельна кар’єра в іншому клубі", "price": 60, "icon": "🗂"},
    "legend": {"title": "Легендарний скаут", "desc": "Вундеркінд 16-17 років з потенціалом 88+ у твоїй команді",
               "price": 45, "icon": "🌟"},
    "xp2": {"title": "Подвійний досвід", "desc": "×2 XP за матчі до кінця дня", "price": 20, "icon": "🚀"},
    "frame": {"title": "Золота рамка тренера", "desc": "Ексклюзивна рамка аватара в профілі", "price": 30, "icon": "👑"},
    "megasponsor": {"title": "Генеральний спонсор", "desc": "+€10 000 000 до бюджету клубу", "price": 80, "icon": "🏦"},
}
GEM_PACKS = [{"id": "g100", "gems": 100, "label": "Жменя кристалів"}, {"id": "g550", "gems": 550, "label": "Скриня"},
             {"id": "g1200", "gems": 1200, "label": "Сейф чемпіона"}]

SHOP = {
    "sponsor": {"title": "Спонсорський контракт", "desc": "+€1 000 000 до бюджету активного клубу", "price": 40,
                "icon": "💼"},
    "medic": {"title": "Медичний штаб", "desc": "Миттєво вилікувати всі травми в команді", "price": 25, "icon": "🩺"},
    "energy": {"title": "Відновлення", "desc": "Повна фізична форма всій команді", "price": 15, "icon": "⚡"},
    "motivation": {"title": "Командний дух", "desc": "+20 до настрою всіх гравців", "price": 15, "icon": "🔥"},
    "camp": {"title": "Тренувальний збір", "desc": "+1 до майстерності 5 гравцям основи (до їх потенціалу)",
             "price": 70, "icon": "🏋️"},
    "scout": {"title": "Скаут-знахідка", "desc": "Талановитий юнак 17 років приєднується до команди", "price": 60,
              "icon": "🔭"},
}


def today() -> str:
    return dt.date.today().isoformat()


@dataclass
class Profile:
    user_id: int
    name: str = "Тренер"
    username: str = ""
    photo_url: str = ""
    coins: int = 20
    gems: int = 25        # premium currency (welcome gift; no real payments yet)
    cosmetics: list = field(default_factory=list)
    xp_boost_until: str = ""
    xp: int = 0
    slots_unlocked: int = FREE_SLOTS
    active_slot: int = 0
    daily_date: str = ""
    daily_streak: int = 0
    day: str = ""
    counters: dict = field(default_factory=dict)
    claimed_today: list = field(default_factory=list)
    achievements: dict = field(default_factory=dict)  # id -> "done" | "claimed"
    unbeaten: int = 0
    last_coins: int = 0
    weekly: dict = field(default_factory=dict)
    reminded: str = ""    # date of the last streak reminder sent by the bot
    h2h: dict = field(default_factory=dict)  # friend uid (str) -> {"w","d","l","last": date}  # {"week", "c": counters, "claimed": [ids], "bonus": bool}

    # ---------- serialisation
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    # ---------- rank
    @property
    def rank(self) -> tuple[str, int, int, int]:
        """(title, level 1.., xp into level, xp needed for next level)"""
        idx = 0
        for i, (need, _) in enumerate(RANKS):
            if self.xp >= need:
                idx = i
        base = RANKS[idx][0]
        nxt = RANKS[idx + 1][0] if idx + 1 < len(RANKS) else base + 3000
        return RANKS[idx][1], idx + 1, self.xp - base, nxt - base

    # ---------- daily
    def roll_day(self) -> None:
        if self.day != today():
            self.day = today()
            self.counters = {}
            self.claimed_today = []

    def daily_available(self) -> bool:
        return self.daily_date != today()

    def daily_amount(self) -> int:
        streak = self.daily_streak + 1 if self._streak_continues() else 1
        return 5 + min(streak, 7) * 2

    def _streak_continues(self) -> bool:
        if not self.daily_date:
            return False
        last = dt.date.fromisoformat(self.daily_date)
        return (dt.date.today() - last).days == 1

    def claim_daily(self) -> tuple[bool, str, int]:
        if not self.daily_available():
            return False, "Щоденну нагороду вже забрано. Повертайся завтра!", 0
        amount = self.daily_amount()
        self.daily_streak = self.daily_streak + 1 if self._streak_continues() else 1
        self.daily_date = today()
        self.coins += amount
        return True, f"+{amount} монет! Серія: {self.daily_streak} дн.", amount

    # ---------- tasks
    def tasks(self) -> list[dict]:
        self.roll_day()
        out = []
        for tid, t in DAILY_TASKS.items():
            prog = min(t["goal"], self.counters.get(t["counter"], 0))
            out.append({"id": tid, "title": t["title"], "goal": t["goal"], "progress": prog, "reward": t["reward"],
                        "done": prog >= t["goal"], "claimed": tid in self.claimed_today, "kind": "daily"})
        for aid, a in ACHIEVEMENTS.items():
            st = self.achievements.get(aid)
            out.append({"id": aid, "title": a["title"], "goal": 1, "progress": 1 if st else 0, "reward": a["reward"],
                        "done": bool(st), "claimed": st == "claimed", "kind": "achievement"})
        return out

    def claimable(self) -> list[dict]:
        return [t for t in self.tasks() if t["done"] and not t["claimed"]]

    def claim_task(self, tid: str) -> tuple[bool, str, int]:
        t = next((x for x in self.tasks() if x["id"] == tid), None)
        if not t or not t["done"]:
            return False, "Завдання ще не виконано.", 0
        if t["claimed"]:
            return False, "Нагороду вже забрано.", 0
        if t["kind"] == "daily":
            self.claimed_today.append(tid)
        else:
            self.achievements[tid] = "claimed"
        self.coins += t["reward"]
        self.xp += t["reward"]
        return True, f"+{t['reward']} монет за «{t['title']}»", t["reward"]

    def achieve(self, aid: str) -> None:
        if aid in ACHIEVEMENTS and aid not in self.achievements:
            self.achievements[aid] = "done"

    # ---------- weekly challenges
    def roll_week(self) -> None:
        if self.weekly.get("week") != week_key():
            self.weekly = {"week": week_key(), "c": {}, "claimed": [], "bonus": False}

    def weekly_ids(self) -> list[str]:
        import random as _r
        ids = sorted(WEEKLY)
        return _r.Random(week_key()).sample(ids, 3)

    def weekly_list(self) -> dict:
        self.roll_week()
        c = self.weekly["c"]
        items = []
        for wid in self.weekly_ids():
            t = WEEKLY[wid]
            prog = min(t["goal"], c.get(t["counter"], 0) if t["counter"] != "streak" else c.get("best_streak", 0))
            items.append({"id": wid, "title": t["title"], "goal": t["goal"], "progress": prog, "coins": t["coins"],
                          "done": prog >= t["goal"], "claimed": wid in self.weekly["claimed"]})
        all_claimed = all(i["claimed"] for i in items)
        return {"week": self.weekly["week"], "items": items, "bonusGems": WEEKLY_BONUS_GEMS,
                "bonusReady": all_claimed and not self.weekly["bonus"], "bonusTaken": self.weekly["bonus"]}

    def claim_weekly(self, wid: str) -> tuple[bool, str]:
        data = self.weekly_list()
        if wid == "bonus":
            if not data["bonusReady"]:
                return False, "Спершу виконай усі три виклики тижня."
            self.weekly["bonus"] = True
            self.gems += WEEKLY_BONUS_GEMS
            return True, f"+{WEEKLY_BONUS_GEMS} 💎 за всі виклики тижня!"
        it = next((i for i in data["items"] if i["id"] == wid), None)
        if not it or not it["done"]:
            return False, "Виклик ще не виконано."
        if it["claimed"]:
            return False, "Нагороду вже забрано."
        self.weekly["claimed"].append(wid)
        self.coins += it["coins"]
        self.xp += it["coins"]
        return True, f"+{it['coins']} монет за «{it['title']}»"

    def on_weekly(self, gf: int, ga: int, conceded_first: bool, cup: bool) -> None:
        self.roll_week()
        c = self.weekly["c"]
        inc = lambda k, n=1: c.__setitem__(k, c.get(k, 0) + n)
        inc("matches")
        inc("goals", gf)
        if gf > ga:
            inc("wins")
            if cup:
                inc("cupwins")
        if ga == 0:
            inc("clean")
        if gf - ga >= 3:
            inc("rout")
        if conceded_first and gf >= ga:
            inc("comeback")
        c["streak"] = c.get("streak", 0) + 1 if gf >= ga else 0
        c["best_streak"] = max(c.get("best_streak", 0), c["streak"])

    # ---------- game hooks
    def on_match(self, gf: int, ga: int) -> int:
        self.roll_day()
        c = self.counters
        c["matches"] = c.get("matches", 0) + 1
        xp = 2
        if gf > ga:
            c["wins"] = c.get("wins", 0) + 1
            xp = 10
            self.achieve("first_win")
        elif gf == ga:
            xp = 4
        if ga == 0:
            c["clean"] = c.get("clean", 0) + 1
        if gf >= 3:
            c["big"] = c.get("big", 0) + 1
        self.last_coins = 6 if gf > ga else 3 if gf == ga else 1
        self.coins += self.last_coins
        if self.xp_boost_until and self.xp_boost_until >= today():
            xp *= 2
        self.unbeaten = self.unbeaten + 1 if gf >= ga else 0
        if self.unbeaten >= 5:
            self.achieve("unbeaten5")
        self.xp += xp
        return xp

    def on_season(self, summary: dict, user_club_id: int) -> int:
        xp = 50
        self.achieve("first_season")
        if summary["position"] <= summary["target"]:
            self.achieve("target_met")
            xp += 50
        if summary["position"] == 1:
            self.achieve("title")
            xp += 150 if summary["division"] == 1 else 60
        if user_club_id in summary.get("promoted", []):
            self.achieve("promotion")
            xp += 60
        self.xp += xp
        return xp

    # ---------- slots
    def unlock_slot(self) -> tuple[bool, str]:
        if self.slots_unlocked >= MAX_SLOTS:
            return False, "Усі слоти вже відкрито."
        price = SLOT_PRICE.get(self.slots_unlocked, 200)
        if self.coins < price:
            return False, f"Потрібно {price} монет."
        self.coins -= price
        self.slots_unlocked += 1
        return True, "Новий слот кар’єри відкрито!"
