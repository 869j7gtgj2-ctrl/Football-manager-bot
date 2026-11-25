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

SHOP = {
    "sponsor": {"title": "Спонсорський контракт", "desc": "+€1 000 000 до бюджету активного клубу", "price": 40,
                "icon": "💼"},
    "medic": {"title": "Медичний штаб", "desc": "Миттєво вилікувати всі травми в команді", "price": 25, "icon": "🩺"},
    "energy": {"title": "Відновлення", "desc": "Повна фізична форма всій команді", "price": 15, "icon": "⚡"},
    "motivation": {"title": "Командний дух", "desc": "+20 до настрою всіх гравців", "price": 15, "icon": "🔥"},
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
