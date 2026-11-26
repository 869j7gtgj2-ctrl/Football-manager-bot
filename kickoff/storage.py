"""SQLite persistence: careers (one JSON blob per user+slot), profiles, hall of fame, real-data cache."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import zlib

from .game.models import World
from .meta import Profile


class Storage:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        c = self.conn
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("CREATE TABLE IF NOT EXISTS careers2 (user_id INTEGER, slot INTEGER, data BLOB NOT NULL,"
                  " updated REAL, PRIMARY KEY (user_id, slot))")
        c.execute("CREATE TABLE IF NOT EXISTS profiles (user_id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS hall (user_id INTEGER PRIMARY KEY, manager TEXT, club TEXT,"
                  " seasons INTEGER, titles INTEGER, promotions INTEGER, score INTEGER, updated REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS realdata (key TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS crests (key TEXT PRIMARY KEY, ctype TEXT, data BLOB, src TEXT, updated REAL)")
        c.commit()

    # ------------------------------------------------------------ profiles
    def profile(self, user_id: int) -> Profile:
        with self._lock:
            row = self.conn.execute("SELECT data FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        p = Profile.from_dict(json.loads(row[0])) if row else Profile(user_id=user_id)
        p.roll_day()
        return p

    def save_profile(self, p: Profile) -> None:
        with self._lock:
            self.conn.execute("REPLACE INTO profiles (user_id, data) VALUES (?, ?)",
                              (p.user_id, json.dumps(p.to_dict(), ensure_ascii=False)))
            self.conn.commit()

    # ------------------------------------------------------------ careers
    def load(self, user_id: int, slot: int | None = None) -> World | None:
        if slot is None:
            slot = self.profile(user_id).active_slot
        with self._lock:
            row = self.conn.execute("SELECT data FROM careers2 WHERE user_id=? AND slot=?", (user_id, slot)).fetchone()
        if not row:
            return None
        w = World.from_dict(json.loads(zlib.decompress(row[0])))
        w.slot = slot
        return w

    def save(self, world: World) -> None:
        blob = zlib.compress(json.dumps(world.to_dict(), ensure_ascii=False).encode(), 6)
        with self._lock:
            self.conn.execute("REPLACE INTO careers2 (user_id, slot, data, updated) VALUES (?, ?, ?, ?)",
                              (world.user_id, world.slot, blob, time.time()))
            self.conn.commit()
        self.update_hall(world)

    def delete(self, user_id: int, slot: int) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM careers2 WHERE user_id=? AND slot=?", (user_id, slot))
            self.conn.commit()

    def slots(self, user_id: int) -> dict[int, World]:
        with self._lock:
            rows = self.conn.execute("SELECT slot, data FROM careers2 WHERE user_id=?", (user_id,)).fetchall()
        out = {}
        for slot, data in rows:
            w = World.from_dict(json.loads(zlib.decompress(data)))
            w.slot = slot
            out[slot] = w
        return out

    # ------------------------------------------------------------ hall of fame
    def update_hall(self, world: World) -> None:
        titles = sum(1 for t in world.trophies if t.startswith("🏆"))
        promos = sum(1 for t in world.trophies if t.startswith("⬆️"))
        seasons = len(world.history)
        score = titles * 100 + promos * 40 + sum(max(0, 21 - h["pos"]) for h in world.history)
        club = world.clubs[world.club_id].name if world.club_id in world.clubs else ""
        with self._lock:
            old = self.conn.execute("SELECT score FROM hall WHERE user_id=?", (world.user_id,)).fetchone()
            if old and old[0] > score:
                return
            self.conn.execute("REPLACE INTO hall VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                              (world.user_id, world.manager, club, seasons, titles, promos, score, time.time()))
            self.conn.commit()

    def top(self, limit: int = 10) -> list[tuple]:
        with self._lock:
            return self.conn.execute(
                "SELECT manager, club, seasons, titles, promotions, score FROM hall ORDER BY score DESC, updated"
                " LIMIT ?", (limit,)).fetchall()

    # ------------------------------------------------------------ real data cache
    def real_get(self, key: str) -> tuple[dict | None, float]:
        with self._lock:
            row = self.conn.execute("SELECT data, updated FROM realdata WHERE key=?", (key,)).fetchone()
        return (json.loads(row[0]), row[1]) if row else (None, 0.0)

    def real_put(self, key: str, data: dict) -> None:
        with self._lock:
            self.conn.execute("REPLACE INTO realdata VALUES (?, ?, ?)", (key, json.dumps(data, ensure_ascii=False),
                                                                        time.time()))
            self.conn.commit()

    def real_all(self) -> dict:
        with self._lock:
            rows = self.conn.execute("SELECT key, data FROM realdata").fetchall()
        return {k: json.loads(d) for k, d in rows}

    # ------------------------------------------------------------ crest images (served by our own server)
    def crest_put(self, key: str, ctype: str, data: bytes, src: str) -> None:
        with self._lock:
            self.conn.execute("REPLACE INTO crests VALUES (?, ?, ?, ?, ?)", (key, ctype, data, src, time.time()))
            self.conn.commit()

    def crest_get(self, key: str) -> tuple[str, bytes] | None:
        with self._lock:
            row = self.conn.execute("SELECT ctype, data FROM crests WHERE key=?", (key,)).fetchone()
        return (row[0], row[1]) if row else None

    def crest_keys(self) -> dict:
        with self._lock:
            rows = self.conn.execute("SELECT key, src FROM crests").fetchall()
        return dict(rows)
