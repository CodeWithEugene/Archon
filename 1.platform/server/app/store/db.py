"""SQLite persistence for missions, attempts, events, and model usage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from app.core.models import Attempt, Event, EventKind, Mission, MissionDetail, ModelUsage

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
  id TEXT PRIMARY KEY, data TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
  id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, iteration INTEGER NOT NULL, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS attempts_mission ON attempts(mission_id);
CREATE TABLE IF NOT EXISTS events (
  mission_id TEXT NOT NULL, id INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, ts TEXT NOT NULL,
  PRIMARY KEY (mission_id, id)
);
CREATE TABLE IF NOT EXISTS usage (
  mission_id TEXT NOT NULL, model TEXT NOT NULL, task TEXT NOT NULL,
  prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL, cost_usd REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS usage_mission ON usage(mission_id);
"""


class Store:
    def __init__(self, path: Path | str) -> None:
        self._path = str(path)
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self._db = await aiosqlite.connect(self._path)
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("store is not open")
        return self._db

    # missions
    async def save_mission(self, m: Mission) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO missions (id, data, status, created_at) VALUES (?, ?, ?, ?)",
            (m.id, m.model_dump_json(), m.status.value, m.created_at.isoformat()),
        )
        await self.db.commit()

    async def get_mission(self, mission_id: str) -> Mission | None:
        async with self.db.execute("SELECT data FROM missions WHERE id = ?", (mission_id,)) as cur:
            row = await cur.fetchone()
        return Mission.model_validate_json(row[0]) if row else None

    async def list_missions(self, limit: int = 50) -> list[Mission]:
        async with self.db.execute("SELECT data FROM missions ORDER BY created_at DESC LIMIT ?", (limit,)) as cur:
            rows = await cur.fetchall()
        return [Mission.model_validate_json(r[0]) for r in rows]

    async def get_detail(self, mission_id: str) -> MissionDetail | None:
        m = await self.get_mission(mission_id)
        if m is None:
            return None
        return MissionDetail(
            **m.model_dump(), attempts=await self.attempts(mission_id), usage=await self.usage(mission_id)
        )

    # attempts
    async def save_attempt(self, a: Attempt) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO attempts (id, mission_id, iteration, data) VALUES (?, ?, ?, ?)",
            (a.id, a.mission_id, a.iteration, a.model_dump_json()),
        )
        await self.db.commit()

    async def attempts(self, mission_id: str) -> list[Attempt]:
        async with self.db.execute(
            "SELECT data FROM attempts WHERE mission_id = ? ORDER BY iteration, id", (mission_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [Attempt.model_validate_json(r[0]) for r in rows]

    # events
    async def save_event(self, e: Event) -> None:
        if e.id == 0:
            return
        await self.db.execute(
            "INSERT OR REPLACE INTO events (mission_id, id, kind, payload, ts) VALUES (?, ?, ?, ?, ?)",
            (e.mission_id, e.id, e.kind.value, json.dumps(e.payload), e.ts.isoformat()),
        )
        await self.db.commit()

    async def events(self, mission_id: str) -> list[Event]:
        async with self.db.execute(
            "SELECT id, kind, payload, ts FROM events WHERE mission_id = ? ORDER BY id", (mission_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [
            Event(id=r[0], mission_id=mission_id, kind=EventKind(r[1]), payload=json.loads(r[2]), ts=r[3]) for r in rows
        ]

    # usage
    async def save_usage(self, u: ModelUsage) -> None:
        await self.db.execute(
            "INSERT INTO usage (mission_id, model, task, prompt_tokens, completion_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?)",
            (u.mission_id, u.model, u.task, u.prompt_tokens, u.completion_tokens, u.cost_usd),
        )
        await self.db.commit()

    async def usage(self, mission_id: str) -> list[ModelUsage]:
        async with self.db.execute(
            "SELECT model, SUM(prompt_tokens), SUM(completion_tokens), SUM(cost_usd) FROM usage WHERE mission_id = ? GROUP BY model",
            (mission_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [
            ModelUsage(
                mission_id=mission_id,
                model=r[0],
                prompt_tokens=int(r[1]),
                completion_tokens=int(r[2]),
                cost_usd=float(r[3]),
            )
            for r in rows
        ]

    async def total_spend(self, mission_id: str) -> float:
        async with self.db.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM usage WHERE mission_id = ?", (mission_id,)
        ) as cur:
            row = await cur.fetchone()
        return float(row[0]) if row else 0.0

    async def raw(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        async with self.db.execute(sql, params) as cur:
            return [tuple(r) for r in await cur.fetchall()]
