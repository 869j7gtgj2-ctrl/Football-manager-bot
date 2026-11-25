"""Background refresh of real squads and crests.

Sources:
- football-data.org (top-5 leagues, needs FOOTBALL_DATA_KEY): squad with positions, dates of birth, nationality, crest.
- Wikipedia (all clubs, no key): current squad template (number, nationality, position, name) and the infobox crest;
  Wikidata for players' dates of birth.
Results are cached per club in the `realdata` table and used when a new career world is generated.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import unicodedata

import aiohttp

from .game.leagues import CLUBS, LEAGUES
from .game.names import COUNTRY, FIFA
from .storage import Storage

log = logging.getLogger(__name__)
UA = {"User-Agent": "KickoffManagerBot/1.0 (private hobby football game; aiohttp)"}
WIKI = "https://en.wikipedia.org/w/api.php"
WIKIDATA = "https://www.wikidata.org/w/api.php"
FD = "https://api.football-data.org/v4"
MAX_AGE = 7 * 86400
COUNTRY_EN = {1: "Ukraine", 2: "Ukraine", 3: "England", 4: "Spain", 5: "Germany", 6: "Italy", 7: "France"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def fd_position(pos: str | None) -> str:
    p = (pos or "").lower()
    if "goal" in p:
        return "GK"
    if "back" in p or "defen" in p:
        return "DF"
    if "wing" in p or "forward" in p or "offen" in p or "striker" in p or "attack" in p:
        return "FW"
    return "MF"


# ------------------------------------------------------------------ football-data.org
async def fetch_fd(session: aiohttp.ClientSession, key: str, code: str) -> list[dict]:
    async with session.get(f"{FD}/competitions/{code}/teams", headers={"X-Auth-Token": key}, timeout=30) as r:
        if r.status != 200:
            log.warning("football-data %s -> HTTP %s", code, r.status)
            return []
        data = await r.json()
    return data.get("teams", [])


def match_team(teams: list[dict], token: str) -> dict | None:
    t = norm(token)
    for team in teams:
        names = " | ".join(norm(team.get(k) or "") for k in ("name", "shortName", "tla"))
        if t in names:
            return team
    return None


def fd_squad(team: dict) -> list[dict]:
    out = []
    for p in team.get("squad") or []:
        if not p.get("name"):
            continue
        out.append({"name": p["name"], "pos": fd_position(p.get("position")), "dob": p.get("dateOfBirth"),
                    "nation": COUNTRY.get(p.get("nationality") or "", "EN"), "number": p.get("shirtNumber") or 0})
    return out


# ------------------------------------------------------------------ Wikipedia
async def wiki(session, **params) -> dict:
    params = {"format": "json", "formatversion": "2", **params}
    async with session.get(WIKI, params=params, headers=UA, timeout=30) as r:
        return await r.json(content_type=None)


async def wiki_title(session, token: str, lid: int) -> str | None:
    q = f"{token} football club {COUNTRY_EN[lid]}"
    data = await wiki(session, action="query", list="search", srsearch=q, srlimit=5)
    hits = data.get("query", {}).get("search", [])
    for h in hits:
        t = h["title"]
        if any(w in t.lower() for w in ("season", "list of", "women", "stadium", "u19", "u21", "reserves")):
            continue
        return t
    return None


TEMPLATE = re.compile(r"\{\{\s*(?:fs player|football squad player|fs2 player)\s*\|(.*?)\}\}", re.I | re.S)
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def clean(v: str) -> tuple[str, str | None]:
    link = None
    m = LINK.search(v)
    if m:
        link = m.group(1).strip()
    v = LINK.sub(lambda m: m.group(2) or m.group(1), v)
    v = re.sub(r"<ref.*?(/>|</ref>)", "", v, flags=re.S)
    v = re.sub(r"\{\{[^{}]*\}\}", "", v)
    v = re.sub(r"<[^>]+>|'''?|\(.*?\)", "", v)
    return v.strip(), link


def parse_squad(text: str) -> list[dict]:
    # only the first-team block: cut before loan / reserve sections
    lower = text.lower()
    start = lower.find("fs start")
    if start < 0:
        start = lower.find("football squad start")
    if start < 0:
        return []
    end = len(text)
    for marker in ("out on loan", "on loan", "reserve", "under-21", "under-19", "academy", "youth"):
        i = lower.find(marker, start + 50)
        if i > 0:
            # the marker must be in a heading or squad title after the start
            head = lower.rfind("\n", 0, i)
            if lower[head:i].strip().startswith(("=", "{{fs mid", "{{fs end")) or "title" in lower[head:i]:
                end = min(end, i)
    block = text[start:end]
    out = []
    for m in TEMPLATE.finditer(block):
        params = {}
        for part in re.split(r"\|(?![^\[]*\]\])", m.group(1)):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip().lower()] = v.strip()
        name, link = clean(params.get("name", ""))
        if not name:
            continue
        pos = (params.get("pos") or "MF").upper()[:2]
        pos = {"GK": "GK", "DF": "DF", "MF": "MF", "FW": "FW"}.get(pos, "MF")
        nat = (params.get("nat") or "").upper().strip()
        try:
            number = int(re.sub(r"\D", "", params.get("no", "")) or 0)
        except ValueError:
            number = 0
        out.append({"name": name, "pos": pos, "nation": FIFA.get(nat, "EN" if nat else "UA"), "number": number,
                    "link": link})
    return out


async def wiki_crest(session, title: str) -> str | None:
    data = await wiki(session, action="query", prop="pageimages", piprop="thumbnail", pithumbsize=200,
                      titles=title, redirects=1)
    pages = data.get("query", {}).get("pages", [])
    for p in pages:
        if p.get("thumbnail"):
            return p["thumbnail"]["source"]
    return None


async def wikidata_dobs(session, links: list[str]) -> dict[str, str]:
    out = {}
    for i in range(0, len(links), 50):
        chunk = links[i:i + 50]
        params = {"action": "wbgetentities", "sites": "enwiki", "titles": "|".join(chunk), "props": "claims|sitelinks",
                  "format": "json", "sitefilter": "enwiki"}
        async with session.get(WIKIDATA, params=params, headers=UA, timeout=40) as r:
            data = await r.json(content_type=None)
        for ent in (data.get("entities") or {}).values():
            title = ((ent.get("sitelinks") or {}).get("enwiki") or {}).get("title")
            claims = (ent.get("claims") or {}).get("P569") or []
            if title and claims:
                try:
                    t = claims[0]["mainsnak"]["datavalue"]["value"]["time"]
                    out[title] = t[1:11]
                except (KeyError, TypeError):
                    pass
        await asyncio.sleep(1)
    return out


async def fetch_wiki_club(session, token: str, lid: int) -> dict | None:
    title = await wiki_title(session, token, lid)
    if not title:
        return None
    data = await wiki(session, action="parse", page=title, prop="wikitext", redirects=1)
    text = (data.get("parse") or {}).get("wikitext") or ""
    squad = parse_squad(text)
    crest = await wiki_crest(session, title)
    links = [p["link"] for p in squad if p.get("link")]
    dobs = await wikidata_dobs(session, links) if links else {}
    for p in squad:
        p["dob"] = dobs.get(p.pop("link", None) or "", None)
    return {"squad": squad, "crest": crest, "source": "wikipedia", "title": title}


# ------------------------------------------------------------------ refresh
async def refresh(storage: Storage, fd_key: str, force: bool = False) -> None:
    async with aiohttp.ClientSession() as session:
        fd_teams: dict[int, list] = {}
        if fd_key:
            for lid, meta in LEAGUES.items():
                if meta.get("fd"):
                    try:
                        fd_teams[lid] = await fetch_fd(session, fd_key, meta["fd"])
                    except Exception:
                        log.exception("football-data fetch failed for %s", meta["fd"])
                    await asyncio.sleep(7)
        for lid, clubs in CLUBS.items():
            for name, _, _, _, token in clubs:
                old, updated = storage.real_get(token)
                if not force and old and time.time() - updated < MAX_AGE:
                    continue
                result = None
                team = match_team(fd_teams.get(lid, []), token) if fd_teams.get(lid) else None
                if team and len(team.get("squad") or []) >= 14:
                    result = {"squad": fd_squad(team), "crest": team.get("crest"), "source": "football-data"}
                try:
                    wres = await fetch_wiki_club(session, token, lid)
                except Exception:
                    log.exception("wikipedia fetch failed for %s", token)
                    wres = None
                if result is None:
                    result = wres
                elif wres and not result.get("crest"):
                    result["crest"] = wres.get("crest")
                if result and (len(result.get("squad") or []) >= 14 or result.get("crest")):
                    storage.real_put(token, result)
                    log.info("real data: %s -> %d players (%s)", name, len(result.get("squad") or []),
                             result.get("source"))
                await asyncio.sleep(1.0)


async def refresh_loop(storage: Storage, fd_key: str) -> None:
    await asyncio.sleep(5)
    while True:
        try:
            await refresh(storage, fd_key)
        except Exception:
            log.exception("real data refresh failed")
        await asyncio.sleep(12 * 3600)
