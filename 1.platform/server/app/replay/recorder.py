"""Record finished missions to JSON and replay them through the event bus."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from app.core.events import EventBus
from app.core.models import Attempt, Event, EventKind, Mission, MissionStatus, new_id, utcnow
from app.store.db import Store

logger = logging.getLogger(__name__)
MAX_GAP_S = 1.5
MIN_GAP_S = 0.04


class Recorder:
    def __init__(self, directory: Path, store: Store, bus: EventBus) -> None:
        self.dir = directory
        self.store = store
        self.bus = bus
        self.dir.mkdir(parents=True, exist_ok=True)

    async def record(self, mission: Mission) -> Path:
        events = self.bus.history(mission.id) or await self.store.events(mission.id)
        attempts = await self.store.attempts(mission.id)
        usage = await self.store.usage(mission.id)
        payload: dict[str, Any] = {
            "version": 1,
            "recorded_at": utcnow().isoformat(),
            "mission": mission.model_dump(mode="json"),
            "attempts": [a.model_dump(mode="json") for a in attempts],
            "usage": [u.model_dump(mode="json") for u in usage],
            "events": [
                {"id": e.id, "kind": e.kind.value, "payload": e.payload, "ts": e.ts.isoformat()} for e in events if e.id
            ],
        }
        path = self.dir / f"{mission.id}.json"
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        logger.info("recorded mission %s to %s (%d events)", mission.id, path, len(payload["events"]))
        return path

    def list(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in sorted(self.dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            m = data.get("mission", {})
            events = data.get("events", [])
            duration = 0.0
            if len(events) >= 2:
                try:
                    from datetime import datetime

                    t0 = datetime.fromisoformat(events[0]["ts"])
                    t1 = datetime.fromisoformat(events[-1]["ts"])
                    duration = (t1 - t0).total_seconds()
                except (KeyError, ValueError):
                    duration = 0.0
            out.append(
                {
                    "id": p.stem,
                    "title": m.get("swe_instance_id")
                    or (m.get("repo_url") or "").replace("https://github.com/", "")
                    or p.stem,
                    "type": m.get("type"),
                    "repo_url": m.get("repo_url"),
                    "swe_instance_id": m.get("swe_instance_id"),
                    "status": m.get("status"),
                    "iterations": m.get("iteration", 0),
                    "resolved": m.get("status") == MissionStatus.VERIFIED.value,
                    "duration_s": round(duration, 1),
                }
            )
        return out

    def load(self, recording_id: str) -> dict[str, Any] | None:
        if "/" in recording_id or ".." in recording_id:
            return None
        p = self.dir / f"{recording_id}.json"
        if not p.exists():
            return None
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
        return data

    async def start_replay(self, recording_id: str, speed: float = 1.0) -> Mission | None:
        data = self.load(recording_id)
        if data is None:
            return None
        src = Mission.model_validate(data["mission"])
        replay = src.model_copy(
            update={
                "id": new_id("rp"),
                "replay_of": recording_id,
                "created_at": utcnow(),
                "finished_at": None,
                "status": MissionStatus.PENDING,
            }
        )
        await self.store.save_mission(replay)
        for raw in data.get("attempts", []):
            a = Attempt.model_validate(raw)
            await self.store.save_attempt(a.model_copy(update={"id": f"{a.id}", "mission_id": replay.id}))
        asyncio.get_running_loop().create_task(self._play(replay, data, speed))
        return replay

    async def _play(self, replay: Mission, data: dict[str, Any], speed: float) -> None:
        from datetime import datetime

        events = data.get("events", [])
        prev: datetime | None = None
        for raw in events:
            try:
                ts = datetime.fromisoformat(raw["ts"])
            except (KeyError, ValueError):
                ts = None
            if prev is not None and ts is not None:
                gap = min(MAX_GAP_S, max(MIN_GAP_S, (ts - prev).total_seconds())) / max(speed, 0.1)
                await asyncio.sleep(gap)
            prev = ts
            kind = EventKind(raw["kind"])
            payload = dict(raw["payload"])
            if kind == EventKind.STATUS and "status" in payload:
                replay.status = MissionStatus(payload["status"])
                replay.iteration = int(payload.get("iteration", replay.iteration))
                await self.store.save_mission(replay)
            await self.bus.publish(replay.id, kind, payload)
        replay.finished_at = utcnow()
        await self.store.save_mission(replay)

    @staticmethod
    def event_from_raw(mission_id: str, raw: dict[str, Any]) -> Event:
        return Event(
            id=int(raw["id"]),
            mission_id=mission_id,
            kind=EventKind(raw["kind"]),
            payload=raw["payload"],
            ts=raw["ts"],
        )
