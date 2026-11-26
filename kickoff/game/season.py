"""Season flow: fixtures, table, rounds, finances, development, season end."""
from __future__ import annotations

import random

from .finance import book

from .generator import club_level, make_player, refresh_free_agents, youth_player
from .match import apply_result, simulate
from .leagues import LEAGUES, PROMOTION
from .models import MatchResult, Offer, World

ROUND_WEEKS = 1


# ---------------------------------------------------------------- fixtures
def round_robin(ids: list[int], rng: random.Random) -> list[list[tuple[int, int]]]:
    ids = list(ids)
    rng.shuffle(ids)
    if len(ids) % 2:
        ids.append(-1)
    n = len(ids)
    rounds = []
    arr = ids[:]
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = arr[i], arr[n - 1 - i]
            if -1 in (a, b):
                continue
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        rounds.append(pairs)
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    second = [[(b, a) for a, b in rnd] for rnd in rounds]
    return rounds + second


def start_season(world: World, rng: random.Random) -> None:
    world.round = 0
    world.results = []
    world.fixtures = {}
    for div in sorted({c.division for c in world.clubs.values()}):
        ids = [c.id for c in world.division_clubs(div)]
        world.fixtures[div] = round_robin(ids, rng)
    for p in world.players.values():
        p.apps = p.goals = p.assists = p.yellows = 0
        p.rating_sum = 0.0
    world.season_finances = {"income": 0, "wages": 0, "transfers_in": 0, "transfers_out": 0}
    world.board_target = board_target(world)
    world.offers = []
    world.add_news(f"Стартував сезон {world.season}. Ціль від правління: топ-{world.board_target}.")
    from . import cups
    cups.setup(world, rng)
    if world.club_id in world.clubs:
        from . import sponsors
        sponsors.on_season_start(world, rng)


def board_target(world: World) -> int:
    club = world.club
    ranked = sorted(world.division_clubs(club.division), key=lambda c: c.reputation, reverse=True)
    rank = [c.id for c in ranked].index(club.id) + 1
    return min(len(ranked), max(1, rank + 1))


# ---------------------------------------------------------------- table
def table(world: World, division: int) -> list[dict]:
    rows = {c.id: {"club": c.id, "p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "pts": 0, "form": []}
            for c in world.division_clubs(division)}
    for r in world.results:
        if r.division != division or r.home not in rows or r.away not in rows:
            continue
        for cid, gf, ga in ((r.home, r.hg, r.ag), (r.away, r.ag, r.hg)):
            row = rows[cid]
            row["p"] += 1
            row["gf"] += gf
            row["ga"] += ga
            if gf > ga:
                row["w"] += 1
                row["pts"] += 3
                row["form"].append("W")
            elif gf == ga:
                row["d"] += 1
                row["pts"] += 1
                row["form"].append("D")
            else:
                row["l"] += 1
                row["form"].append("L")
    out = list(rows.values())
    out.sort(key=lambda x: (x["pts"], x["gf"] - x["ga"], x["gf"], -x["club"]), reverse=True)
    return out


def position(world: World, club_id: int) -> int:
    div = world.clubs[club_id].division
    return [r["club"] for r in table(world, div)].index(club_id) + 1


def next_fixture(world: World) -> tuple[int, int] | None:
    rounds = world.fixtures.get(world.club.division, [])
    if world.round >= len(rounds):
        return None
    for h, a in rounds[world.round]:
        if world.club_id in (h, a):
            return h, a
    return None


def season_over(world: World) -> bool:
    from . import cups
    return world.round >= len(world.fixtures.get(world.club.division, [])) and not cups.due(world)


# ---------------------------------------------------------------- economy
def fair_ticket(club) -> int:
    money = LEAGUES.get(club.division, {}).get("money", 1.0)
    return int(max(5, 6 + (club.reputation - 55) * 0.9 * (0.6 + money / 4)))


def gate_income(world: World, club, rng: random.Random) -> tuple[int, int]:
    form_bonus = 0.0
    rows = [r for r in table(world, club.division) if r["club"] == club.id]
    if rows:
        last = rows[0]["form"][-5:]
        form_bonus = (last.count("W") - last.count("L")) * 0.02
    fill = 0.78 + form_bonus - (club.ticket_price - fair_ticket(club)) * 0.035
    fill = max(0.12, min(1.0, fill + rng.uniform(-0.05, 0.05)))
    att = int(club.stadium * fill)
    return att, att * club.ticket_price


def sponsor_income(club) -> int:
    return int(club.sponsor or club.reputation ** 2 * 12)


def wage_bill(world: World, club_id: int) -> int:
    total = sum(p.wage for p in world.squad(club_id))
    if club_id == world.club_id and world.staff:
        from .staff import staff_wages
        total += staff_wages(world)
    return total


# ---------------------------------------------------------------- development
def growth_base(age: int) -> float:
    if age <= 19:
        return 7.0
    if age <= 21:
        return 5.0
    if age <= 23:
        return 3.5
    if age <= 26:
        return 1.8
    if age <= 28:
        return 0.6
    return 0.0


def develop(world: World, club, played: set[int], rng: random.Random, rounds: int) -> list[str]:
    msgs = []
    focus = world.training if club.is_user else "balanced"
    staff = world.staff if club.is_user else {}
    st = lambda r: staff[r]["level"] if r in staff else 0
    for p in world.squad(club.id):
        # recovery
        rec = 18 + (8 if focus == "fitness" else 0) + club.training_level + 3 * st("fitness")
        p.fitness = min(100, p.fitness + rec)
        p.morale += (70 - p.morale) // 10
        if p.skill >= p.potential:
            continue
        mult = (0.7 + 0.15 * club.training_level) * (1 + 0.08 * st("assistant"))
        if focus == "youth" and p.age <= 21:
            mult *= 1.3
        elif focus == "attack" and p.pos in ("FW", "MF"):
            mult *= 1.2
        elif focus == "defense" and p.pos in ("DF", "GK"):
            mult *= 1.2
        elif focus == "fitness":
            mult *= 0.85
        mult *= 1.15 if p.id in played else 0.85
        if rng.random() < growth_base(p.age) * mult / max(rounds, 1):
            p.skill += 1
            if club.is_user and p.skill % 5 == 0:
                msgs.append(f"📈 {p.name} прогресує: тепер {p.skill}")
    return msgs


# ---------------------------------------------------------------- AI market
def ai_transfers(world: World, rng: random.Random) -> None:
    if not world.transfer_window_open() or rng.random() > 0.45:
        return
    ai = [c for c in world.clubs.values() if not c.is_user]
    club = rng.choice(ai)
    squad = world.squad(club.id)
    by_pos = {}
    for p in squad:
        by_pos.setdefault(p.pos, []).append(p)
    need = {"GK": 2, "DF": 7, "MF": 7, "FW": 4}
    pos = min(need, key=lambda k: (len(by_pos.get(k, [])) - need[k], sum(x.skill for x in by_pos.get(k, [])) / max(1, len(by_pos.get(k, [])))))
    worst = min((p for p in by_pos.get(pos, []) if not p.loan), key=lambda p: p.skill, default=None)
    cands = [p for p in world.free_agents() if p.pos == pos and (worst is None or p.skill > worst.skill)
             and p.skill <= club_level(club.reputation) + 8]
    if cands:
        signing = max(cands, key=lambda p: p.skill)
        signing.club_id = club.id
        signing.wage = signing.fair_wage()
        signing.contract = rng.randint(1, 3)
        if signing.skill >= 65:
            world.add_news(f"🔁 {club.name} підписав вільного агента {signing.name} ({signing.skill}).")
    if len(world.squad(club.id)) > 27 and worst:
        worst.club_id = None
        worst.listed = False


def generate_offers(world: World, rng: random.Random) -> None:
    from .transfers import generate_pitches, round_fee
    keep = [o for o in world.offers if o.kind == "final"]
    world.offers = []
    generate_pitches(world, rng)
    if not world.transfer_window_open():
        world.negotiations = {}
        return
    world.offers = keep
    buyers = [c for c in world.clubs.values() if not c.is_user]
    for p in world.squad(world.club_id):
        if p.loan or any(o.player_id == p.id for o in world.offers):
            continue
        val = p.value()
        if p.listed:
            ratio = (p.ask or val) / max(1, val)
            chance = 0.55 if ratio <= 1 else 0.35 if ratio <= 1.25 else 0.15 if ratio <= 1.5 else 0.04
        else:
            chance = 0.05 if p.skill >= club_level(world.club.reputation) + 3 else 0.01
        if rng.random() >= chance:
            continue
        rich = [c for c in buyers if c.budget > val * 0.8 and club_level(c.reputation) + 10 >= p.skill]
        if not rich:
            continue
        buyer = rng.choice(rich)
        if p.listed and p.ask:
            fee = p.ask * rng.uniform(0.82, 1.0) if p.ask <= val * 1.3 else val * rng.uniform(0.95, 1.25)
        else:
            fee = val * rng.uniform(1.0, 1.45)
        fee = round_fee(fee)
        top = round_fee(max(fee, min(buyer.budget * 0.9, fee * rng.uniform(1.06, 1.22))))
        world.offers.append(Offer(id=world.new_id(), player_id=p.id, club_id=buyer.id, fee=fee, max_fee=top))
    if world.offers:
        world.add_news(f"📨 Трансферні пропозиції: {len(world.offers)}.")


# ---------------------------------------------------------------- round
def play_round(world: World, rng: random.Random | None = None, user_res: dict | None = None) -> dict | None:
    rng = rng or random.Random()
    if world.round >= len(world.fixtures.get(world.club.division, [])):
        return None
    r = world.round
    total = len(world.fixtures[world.club.division])
    unavailable_start = {p.id: (p.injured, p.suspended) for p in world.players.values() if p.injured or p.suspended}
    injected, user_res = user_res, None
    played: set[int] = set()
    league_ratings: dict = {}
    for div, rounds in world.fixtures.items():
        n = len(rounds)
        lo, hi = (r * n) // total, ((r + 1) * n) // total
        for h, a, rr in [(h, a, k) for k in range(lo, hi) for h, a in rounds[k]]:
            home, away = world.clubs[h], world.clubs[a]
            detailed = world.club_id in (h, a)
            if injected and (injected["home"], injected["away"]) == (h, a):
                res = injected
            else:
                res = simulate(world, home, away, rng, detailed=detailed)
            apply_result(world, res, rng)
            played.update(int(k) for k in res["minutes"])
            if div == world.club.division:
                league_ratings.update(res.get("ratings", {}))
            world.results.append(MatchResult(round=rr, division=div, home=h, away=a, hg=res["hg"], ag=res["ag"]))
            att, gate = gate_income(world, home, rng)
            home.budget += gate
            res["attendance"] = att
            if home.is_user:
                world.season_finances["income"] += gate
                book(world, "gate", gate)
            if detailed:
                user_res = res
    # ticks for players who were unavailable before this round
    for pid, (inj, sus) in unavailable_start.items():
        p = world.players.get(pid)
        if not p:
            continue
        if inj and p.injured:
            p.injured -= 1
            if p.injured == 0 and p.club_id == world.club_id:
                world.add_news(f"🩹 {p.name} відновився після травми.")
        if sus and p.suspended:
            p.suspended -= 1
    # weekly finances + development
    msgs = []
    for club in world.clubs.values():
        wages = wage_bill(world, club.id)
        spon = sponsor_income(club)
        club.budget += spon - wages
        if club.is_user:
            world.season_finances["wages"] += wages
            world.season_finances["income"] += spon
            book(world, "wages", wages)
            book(world, "commercial", spon)
        elif club.budget < 0:
            club.budget = max(club.budget, -500_000)
        msgs += develop(world, club, played, rng, total)
    from .schedule import team_of_week
    msgs = team_of_week(world, league_ratings, r + 1) + msgs
    for m in msgs[:3]:
        world.add_news(m)
    # board confidence
    if user_res:
        is_home = user_res["home"] == world.club_id
        gf, ga = (user_res["hg"], user_res["ag"]) if is_home else (user_res["ag"], user_res["hg"])
        opp = world.clubs[user_res["away"] if is_home else user_res["home"]]
        diff = world.club.reputation - opp.reputation
        if gf > ga:
            delta = 3 if diff > 10 else 5
        elif gf == ga:
            delta = -2 if diff > 10 else 1
        else:
            delta = -6 if diff > 10 else -3
        if world.club.budget < 0:
            delta -= 3
        world.confidence = max(0, min(100, world.confidence + delta))
        world.last_match = _serialisable(user_res)
    world.round += 1
    from . import sponsors
    sponsors.on_round(world)
    ai_transfers(world, rng)
    generate_offers(world, rng)
    if world.confidence <= 0:
        world.fired = True
        world.add_news("🚪 Правління звільнило тебе з посади головного тренера.")
    return user_res


def user_fixture(world: World) -> dict | None:
    """The user's next match on the calendar: {"home", "away", "comp"} (comp is None for the league)."""
    from . import cups
    cups.ensure(world)
    ev = cups.user_next(world)
    if ev:
        return {"home": ev["home"], "away": ev["away"], "comp": ev["key"]}
    nf = next_fixture(world)
    return {"home": nf[0], "away": nf[1], "comp": None} if nf else None


def play_next(world: World, rng: random.Random | None = None, user_res: dict | None = None) -> dict | None:
    """Next step of the calendar: due cup/European stages first, then the league round."""
    rng = rng or random.Random()
    from . import cups
    cups.ensure(world, rng)
    for _ in range(40):
        pending = cups.due(world)
        if not pending:
            break
        res = cups.play_stage(world, pending[0], rng, user_res)
        if res:
            world.last_match = _serialisable(res)
            return res
    return play_round(world, rng, user_res)


def _serialisable(res: dict) -> dict:
    out = dict(res)
    for k in ("minutes", "ratings", "goals_by", "assists_by", "yellows", "fatigue"):
        out[k] = {str(a): b for a, b in res[k].items()}
    return out


# ---------------------------------------------------------------- season end
def prizes(div: int) -> tuple[int, int]:
    money = LEAGUES.get(div, {}).get("money", 1.0)
    return int(money * 2_500_000), int(money * 180_000)


def end_season(world: World, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    summary: dict = {"season": world.season, "divisions": {}}
    divisions = sorted(world.fixtures)
    tables = {d: table(world, d) for d in divisions}
    # awards and prizes
    for d in divisions:
        rows = tables[d]
        champion = rows[0]["club"]
        bonus, step = prizes(d)
        for i, row in enumerate(rows):
            club = world.clubs[row["club"]]
            prize = (len(rows) - i) * step + (bonus if i == 0 else 0)
            club.budget += prize
            if club.is_user:
                world.season_finances["income"] += prize
                summary["prize"] = prize
                book(world, "prize", prize, f"Призові за {i + 1}-е місце в лізі")
            # reputation drift
            expected = sorted(rows, key=lambda r: world.clubs[r["club"]].reputation, reverse=True)
            exp_pos = [r["club"] for r in expected].index(club.id)
            club.reputation = max(15, min(95, club.reputation + int((exp_pos - i) * 0.8) + (3 if i == 0 else 0)))
        scorers = sorted((p for p in world.players.values() if p.club_id and world.clubs[p.club_id].division == d),
                         key=lambda p: (p.goals, p.assists), reverse=True)
        best = max((p for p in world.players.values() if p.club_id and world.clubs[p.club_id].division == d
                    and p.apps >= 10), key=lambda p: p.avg_rating, default=None)
        summary["divisions"][d] = {
            "champion": champion,
            "top_scorer": (scorers[0].id, scorers[0].goals) if scorers else None,
            "best_player": (best.id, best.avg_rating) if best else None,
        }
    # user evaluation
    user_div = world.club.division
    pos = [r["club"] for r in tables[user_div]].index(world.club_id) + 1
    summary["position"] = pos
    summary["division"] = user_div
    summary["target"] = world.board_target
    if pos == 1:
        world.trophies.append(f"🏆 Чемпіон: {LEAGUES[user_div]['short']} (сезон {world.season})")
    if pos <= world.board_target:
        world.confidence = min(100, world.confidence + 15 + (world.board_target - pos) * 3)
    else:
        world.confidence = max(0, world.confidence - (pos - world.board_target) * 8)
    from . import cups
    cups.qualify(world, tables)
    summary["cups"] = {k: {"name": c["name"], "winner": c.get("winner")} for k, c in (world.cups or {}).items()}
    # promotion / relegation
    summary["relegated"], summary["promoted"] = [], []
    for upper, lower, n in PROMOTION:
        if upper not in tables or lower not in tables:
            continue
        down = [r["club"] for r in tables[upper][-n:]]
        up = [r["club"] for r in tables[lower][:n]]
        for cid in down:
            world.clubs[cid].division = lower
        for cid in up:
            world.clubs[cid].division = upper
        summary["relegated"] += down
        summary["promoted"] += up
    if True:
        down, up = summary["relegated"], summary["promoted"]
        if world.club_id in down:
            world.confidence = max(0, world.confidence - 25)
        if world.club_id in up:
            world.confidence = min(100, world.confidence + 20)
            world.trophies.append(f"⬆️ Підвищення в класі (сезон {world.season})")
    world.history.append({"season": world.season, "club": world.club_id, "division": user_div, "pos": pos,
                          "target": world.board_target,
                          "pts": tables[user_div][pos - 1]["pts"]})
    if world.confidence <= 0:
        world.fired = True
    from .loans import return_all
    summary["loans"] = return_all(world)
    # aging, retirement, contracts
    retired, left = [], []
    for p in list(world.players.values()):
        p.age += 1
        if p.age >= 30:
            p.skill = max(20, p.skill - rng.randint(0 if p.age < 32 else 1, 2 if p.age < 32 else 4))
        if p.age >= 27:
            p.potential = max(p.skill, min(p.potential, p.skill + (2 if p.age < 29 else 0)))
        p.injured = 0
        p.suspended = 0
        p.fitness = 100
        if (p.age >= 34 and rng.random() < 0.45) or p.age >= 37 or (p.club_id is None and p.age >= 33):
            if p.club_id == world.club_id:
                retired.append(p.name)
            del world.players[p.id]
            continue
        if p.club_id is None:
            continue
        p.contract -= 1
        if p.contract <= 0:
            if p.club_id == world.club_id:
                left.append(p.name)
                p.club_id = None
                p.listed = p.resting = False
            elif rng.random() < 0.75:
                p.contract = rng.randint(1, 3)
                p.wage = p.fair_wage()
            else:
                p.club_id = None
        p.youth = p.youth and p.age <= 18
    summary["retired"], summary["left"] = retired, left
    # youth and squad replenishment
    youth = []
    for club in world.clubs.values():
        n = 2 + (1 if club.academy_level >= 3 else 0) + (1 if club.academy_level >= 5 else 0)
        for _ in range(n if club.is_user else 1):
            y = youth_player(world, rng, club)
            if club.is_user and "scout" in world.staff:
                y.potential = min(96, y.potential + 2 * world.staff["scout"]["level"])
            world.players[y.id] = y
            if club.is_user:
                youth.append(y.id)
        while not club.is_user and len(world.squad(club.id)) < 22:
            counts = {k: 0 for k in ("GK", "DF", "MF", "FW")}
            for p in world.squad(club.id):
                counts[p.pos] += 1
            need = {"GK": 3, "DF": 7, "MF": 7, "FW": 5}
            pos = max(need, key=lambda k: need[k] - counts[k])
            p = make_player(world, rng, pos, club_level(club.reputation), club.id)
            world.players[p.id] = p
    # board safety net: never let the user's squad fall below the minimum
    from .models import SQUAD_MIN
    emergency = []
    while len(world.squad(world.club_id)) < SQUAD_MIN:
        counts = {k: 0 for k in ("GK", "DF", "MF", "FW")}
        for p in world.squad(world.club_id):
            counts[p.pos] += 1
        need = {"GK": 2, "DF": 5, "MF": 5, "FW": 3}
        pos = max(need, key=lambda k: need[k] - counts[k])
        p = make_player(world, rng, pos, club_level(world.club.reputation) - 6, world.club_id)
        p.contract = 1
        world.players[p.id] = p
        emergency.append(p.name)
    summary["youth"] = youth
    summary["emergency"] = emergency
    refresh_free_agents(world, rng)
    from . import sponsors
    from .finance import close_season
    summary["sponsor"] = sponsors.on_season_end(world, summary["position"])
    close_season(world)
    world.season += 1
    start_season(world, rng)
    return summary
