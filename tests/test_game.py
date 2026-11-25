import json
import random

from kickoff.game import new_world, start_career
from kickoff.game.match import pick_lineup, simulate
from kickoff.game.models import World
from kickoff.game.season import end_season, play_round, round_robin, season_over, table
from kickoff.game import transfers as tr


def career(seed=1, div=2):
    w = new_world(1, "Тест", seed=seed)
    cid = [c.id for c in w.clubs.values() if c.division == div][3]
    return start_career(w, cid, random.Random(seed))


def test_round_robin_everyone_plays_everyone_twice():  # noqa
    ids = list(range(12))
    rounds = round_robin(ids, random.Random(0))
    assert len(rounds) == 22
    pairs = [m for r in rounds for m in r]
    assert len(pairs) == 132 and len(set(pairs)) == 132
    for r in rounds:
        teams = [t for m in r for t in m]
        assert len(teams) == len(set(teams)) == 12


def test_lineup_has_eleven_and_one_keeper():
    w = career()
    lu = pick_lineup(w, w.club)
    assert len(lu) == 11
    assert sum(1 for s, _ in lu if s == "GK") == 1


def test_stronger_team_wins_more():
    w = career(div=1)
    clubs = sorted(w.division_clubs(1), key=lambda c: c.reputation)
    weak, strong = clubs[0], clubs[-1]
    rng = random.Random(3)
    wins = losses = 0
    for _ in range(200):
        r = simulate(w, strong, weak, rng)
        wins += r["hg"] > r["ag"]
        losses += r["hg"] < r["ag"]
    assert wins > losses * 2


def test_full_seasons_and_roundtrip():
    w = career()
    rng = random.Random(5)
    for _ in range(2):
        while not season_over(w):
            play_round(w, rng)
        for lid in w.fixtures:
            rows = table(w, lid)
            assert all(r["p"] == (len(rows) - 1) * 2 for r in rows), lid
        s = end_season(w, rng)
        assert s["position"] >= 1
        assert len(w.squad(w.club_id)) >= 16
    w2 = World.from_dict(json.loads(json.dumps(w.to_dict())))
    assert w2.club.name == w.club.name and len(w2.players) == len(w.players)
    play_round(w2, rng)


def test_buy_and_sell_moves_money():
    w = career(div=1)
    w.club.budget = 50_000_000
    target = min((p for p in w.players.values() if p.club_id not in (None, w.club_id)), key=lambda p: p.skill)
    price = tr.asking_price(w, target.id)
    before = w.club.budget
    ok, _ = tr.buy(w, target.id)
    assert ok and target.club_id == w.club_id and w.club.budget == before - price
    ok, _ = tr.quick_sell(w, target.id, random.Random(1))
    assert ok and target.club_id != w.club_id


def test_transfer_window_closed_mid_season():
    w = career()
    w.round = 6
    other = next(p for p in w.players.values() if p.club_id not in (None, w.club_id))
    ok, msg = tr.buy(w, other.id)
    assert not ok and "вікно" in msg


def test_roles_and_custom_lineup():
    import random
    from kickoff.game import new_world, start_career
    from kickoff.game.match import pick_lineup, chemistry, simulate
    from kickoff.game.roles import ROLES, FORMATIONS
    from kickoff.web.server import lineup_action, lineup_json
    w = new_world(1, "T", seed=7)
    cid = next(c.id for c in w.clubs.values() if c.division == 3)
    start_career(w, cid)
    assert all(p.role in ROLES for p in w.players.values())
    lj = lineup_json(w)
    assert len(lj["slots"]) == 11 and all(s["player"] for s in lj["slots"])
    a, b = lj["slots"][1]["player"]["id"], lj["slots"][9]["player"]["id"]
    ok, _ = lineup_action(w, {"action": "assign", "slot": 1, "player": b})
    assert ok
    lu = pick_lineup(w, w.club)
    assert lu[1][1].id == b and lu[9][1].id == a  # swapped
    ok, _ = lineup_action(w, {"action": "formation", "formation": "3-5-2"})
    assert ok and [r for r, _ in pick_lineup(w, w.club)] == [r for r, _, _ in FORMATIONS["3-5-2"]]
    assert 0 <= chemistry(w, w.club, pick_lineup(w, w.club)) <= 100
    lineup_action(w, {"action": "auto"})
    opp = next(c for c in w.division_clubs(3) if c.id != cid)
    res = simulate(w, w.club, opp, random.Random(1))
    assert len(res["xi"][0]) == 11
