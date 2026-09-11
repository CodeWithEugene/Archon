"""Tracks running missions so they can be aborted and counted."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from app.core.runner import MissionRunner


class Registry:
    def __init__(self, *, live_per_ip_per_hour: int = 3, max_concurrent: int = 3) -> None:
        self._runners: dict[str, MissionRunner] = {}
        self._tasks: dict[str, asyncio.Task[object]] = {}
        self._ip_hits: dict[str, list[float]] = defaultdict(list)
        self.live_per_ip_per_hour = live_per_ip_per_hour
        self.max_concurrent = max_concurrent

    def start(self, runner: MissionRunner) -> None:
        task = asyncio.get_running_loop().create_task(runner.run())
        self._runners[runner.m.id] = runner
        self._tasks[runner.m.id] = task
        mission_id = runner.m.id

        def _done(_t: asyncio.Task[object]) -> None:
            self._cleanup(mission_id)

        task.add_done_callback(_done)

    def _cleanup(self, mission_id: str) -> None:
        self._runners.pop(mission_id, None)
        self._tasks.pop(mission_id, None)

    def abort(self, mission_id: str, reason: str = "aborted by user") -> bool:
        runner = self._runners.get(mission_id)
        if runner is None:
            return False
        runner.abort(reason)
        return True

    @property
    def running(self) -> int:
        return len(self._runners)

    def allow_live(self, ip: str) -> bool:
        now = time.time()
        hits = [t for t in self._ip_hits[ip] if now - t < 3600]
        self._ip_hits[ip] = hits
        if len(hits) >= self.live_per_ip_per_hour or self.running >= self.max_concurrent:
            return False
        hits.append(now)
        return True

    async def shutdown(self) -> None:
        for mid in list(self._runners):
            self.abort(mid, "server shutting down")
        for task in list(self._tasks.values()):
            task.cancel()
