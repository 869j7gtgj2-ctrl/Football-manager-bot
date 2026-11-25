"""SQLite persistence: one JSON blob per career plus a hall-of-fame table."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import zlib

from .game.models import World


class Storage:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS careers (user_id INTEGER PRIMARY KEY, data BLOB NOT NULL, updated REAL)")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS hall (user_id INTEGER PRIMARY KEY, manager TEXT, club TEXT, seasons INTEGER,"
            " titles INTEGER, promotions INTEGER, score INTEGER, updated REAL)")
        self.conn.commit()

    def load(self, user_id: int) -> World | None:
        with self._lock:
            row = self.conn.execute("SELECT data FROM careers WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return None
        return World.from_dict(json.loads(zlib.decompress(row[0])))

    def save(self, world: World) -> None:
        blob = zlib.compress(json.dumps(world.to_dict(), ensure_ascii=False).encode(), 6)
        with self._lock:
            self.conn.execute("REPLACE INTO careers (user_id, data, updated) VALUES (?, ?, ?)",
                              (world.user_id, blob, time.time()))
            self.conn.commit()
        self.update_hall(world)

    def delete(self, user_id: int) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM careers WHERE user_id=?", (user_id,))
            self.conn.commit()

    def update_hall(self, world: World) -> None:
        titles = sum(1 for t in world.trophies if t.startswith("🏆"))
        promos = sum(1 for t in world.trophies if t.startswith("⬆️"))
        seasons = len(world.history)
        score = titles * 100 + promos * 40 + sum(max(0, 13 - h["pos"]) * (3 if h["division"] == 1 else 1)
                                                  for h in world.history)
        with self._lock:
            old = self.conn.execute("SELECT score FROM hall WHERE user_id=?", (world.user_id,)).fetchone()
            if old and old[0] > score:
                return  # keep personal best career
            self.conn.execute("REPLACE INTO hall VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                              (world.user_id, world.manager, world.clubs[world.club_id].name if world.club_id in world.clubs else "", seasons,
                               titles, promos, score, time.time()))
            self.conn.commit()

    def top(self, limit: int = 10) -> list[tuple]:
        with self._lock:
            return self.conn.execute(
                "SELECT manager, club, seasons, titles, promotions, score FROM hall ORDER BY score DESC, updated"
                " LIMIT ?", (limit,)).fetchall()
