import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from aiohttp.test_utils import TestClient, TestServer

from kickoff.service import Service
from kickoff.storage import Storage
from kickoff.web.server import check_init_data, create_app

TOKEN = "123:TEST"


def signed(user: dict) -> str:
    pairs = {"auth_date": str(int(time.time())), "query_id": "x", "user": json.dumps(user)}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def test_init_data_validation():
    data = signed({"id": 5, "first_name": "A"})
    assert check_init_data(data, TOKEN)["id"] == 5
    assert check_init_data(data, "999:OTHER") is None
    assert check_init_data(data.replace("query_id=x", "query_id=y"), TOKEN) is None


@pytest.mark.asyncio
async def test_full_flow(tmp_path):
    app = create_app(Service(Storage(str(tmp_path / "db.sqlite"))), TOKEN)
    async with TestClient(TestServer(app)) as c:
        h = {"X-Init-Data": signed({"id": 77, "first_name": "Ілля", "username": "illia"})}
        r = await c.get("/api/profile")
        assert r.status == 401
        prof = (await (await c.get("/api/profile", headers=h)).json())["data"]
        assert prof["coins"] == 20 and prof["slots"][2]["state"] == "locked"
        draft = (await (await c.post("/api/career/draft", json={"slot": 0}, headers=h)).json())["data"]
        assert len(draft["leagues"]) == 7
        club = next(x for l in draft["leagues"] for x in l["clubs"] if x["name"] == "Шахтар")
        prof = (await (await c.post("/api/career/create", json={"slot": 0, "club_id": club["id"]}, headers=h)).json())["data"]
        assert prof["slots"][0]["career"]["club"]["name"] == "Шахтар"
        team = (await (await c.get("/api/team", headers=h)).json())["data"]
        assert sum(len(g["players"]) for g in team["groups"]) == team["count"]
        for _ in range(2):
            res = (await (await c.post("/api/match/play", json={"fast": True}, headers=h)).json())["data"]
            assert "hg" in res and res["xp"] > 0
        # live match: first half, half-time decisions, second half
        ht = (await (await c.post("/api/match/play", json={}, headers=h)).json())["data"]
        assert ht["half"] and ht["minute"] == 45 and len(ht["lineup"]) == 11 and ht["bench"]
        assert all(e["min"] <= 45 for e in ht["events"])
        sub = [[ht["lineup"][-1]["id"], ht["bench"][0]["id"]]]
        res = (await (await c.post("/api/match/second", json={"talk": "fire", "style": "attacking", "subs": sub},
                                   headers=h)).json())["data"]
        assert "hg" in res and res["xp"] > 0 and res["press"]
        assert any(e["type"] == "sub" and e["in"] == sub[0][1] for e in res["events"])
        j = await (await c.post("/api/press", json={"answer": res["press"]["answers"][0]["id"]}, headers=h)).json()
        assert j["ok"] and j["data"]["press"] is None
        m = (await (await c.get("/api/match", headers=h)).json())["data"]
        assert m["predict"]["home"] + m["predict"]["draw"] + m["predict"]["away"] == 100
        rec = (await (await c.get("/api/records", headers=h)).json())["data"]
        assert rec["matches"] == 3
        for path in ("/api/match", "/api/table?league=3", "/api/market?f=FW", "/api/club", "/api/market?f=FA&q=a"):
            j = await (await c.get(path, headers=h)).json()
            assert j["ok"], path
        j = await (await c.post("/api/tactics", json={"formation": "4-3-3", "style": "pressing"}, headers=h)).json()
        assert j["data"]["tactics"]["formation"] == "4-3-3"
        j = await (await c.post("/api/daily", json={}, headers=h)).json()
        assert j["ok"] and j["data"]["coins"] > 20
        j = await (await c.post("/api/task", json={"id": "play3"}, headers=h)).json()
        assert j["ok"]
        j = await (await c.post("/api/shop", json={"item": "energy"}, headers=h)).json()
        assert j["ok"]
        r = await c.get("/")
        assert r.status == 200


@pytest.mark.asyncio
async def test_season_report_sent_to_chat(tmp_path):
    svc = Service(Storage(str(tmp_path / "db.sqlite")))
    sent = []

    async def notify(uid, text):
        sent.append((uid, text))
    svc.notify = notify
    app = create_app(svc, TOKEN)
    async with TestClient(TestServer(app)) as c:
        h = {"X-Init-Data": signed({"id": 9, "first_name": "Ілля"})}
        draft = (await (await c.post("/api/career/draft", json={"slot": 0}, headers=h)).json())["data"]
        club = next(x for l in draft["leagues"] for x in l["clubs"] if x["name"] == "Полтава")
        await c.post("/api/career/create", json={"slot": 0, "club_id": club["id"]}, headers=h)
        while True:
            j = await (await c.post("/api/match/play", json={"fast": True}, headers=h)).json()
            if not j["ok"] or j["data"]["seasonOver"]:
                break
        j = await (await c.post("/api/season/end", json={}, headers=h)).json()
        assert j["ok"]
        report = [t for _, t in sent if "Сезон 2026/27 завершено" in t]
        assert report and "Рівень" in report[0] and "▰" in report[0] + "▱"
