"""Club bookkeeping for the user's club: income/expense by category, notable operations, season history."""
from __future__ import annotations

INCOME = {"gate": ("🎟", "Квитки і матчдей"), "prize": ("🏆", "Призові"), "commercial": ("🛍", "Комерція і ТБ"),
          "sponsor": ("🤝", "Генеральний спонсор"), "sales": ("📤", "Продаж гравців"), "owner": ("💼", "Інвестиції")}
EXPENSE = {"wages": ("💸", "Зарплати"), "transfers": ("📥", "Купівля гравців"), "bonus": ("✍️", "Бонуси за підпис"),
           "staff": ("👔", "Тренерський штаб"), "infra": ("🏗", "Інфраструктура"), "comp": ("⚖️", "Компенсації")}


def book(w, cat: str, amount: int, note: str | None = None) -> None:
    """Record money for the user's club. amount is positive for both incomes and expenses."""
    if amount <= 0:
        return
    w.fin[cat] = w.fin.get(cat, 0) + int(amount)
    if note:
        sign = 1 if cat in INCOME else -1
        w.ledger.insert(0, {"season": w.season, "round": w.round, "cat": cat, "amount": sign * int(amount), "text": note})
        del w.ledger[40:]


def close_season(w) -> None:
    w.fin_history.insert(0, {"season": w.season, **w.fin})
    del w.fin_history[8:]
    w.fin = {}


def totals(w) -> tuple[int, int]:
    inc = sum(v for k, v in w.fin.items() if k in INCOME)
    exp = sum(v for k, v in w.fin.items() if k in EXPENSE)
    return inc, exp
