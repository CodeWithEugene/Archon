"""In-process event bus with per-mission history and SSE-friendly subscriptions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.core.models import Event, EventKind

Sink = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self, max_history: int = 20_000) -> None:
        self._history: dict[str, list[Event]] = {}
        self._conds: dict[str, asyncio.Condition] = {}
        self._closed: set[str] = set()
        self._sinks: list[Sink] = []
        self._max_history = max_history

    def add_sink(self, sink: Sink) -> None:
        self._sinks.append(sink)

    def _cond(self, mission_id: str) -> asyncio.Condition:
        cond = self._conds.get(mission_id)
        if cond is None:
            cond = asyncio.Condition()
            self._conds[mission_id] = cond
        return cond

    def history(self, mission_id: str) -> list[Event]:
        return list(self._history.get(mission_id, []))

    def is_closed(self, mission_id: str) -> bool:
        return mission_id in self._closed

    async def publish(self, mission_id: str, kind: EventKind, payload: dict[str, Any]) -> Event:
        hist = self._history.setdefault(mission_id, [])
        if len(hist) >= self._max_history:
            raise RuntimeError(f"event history for {mission_id} exceeded {self._max_history} events")
        event = Event(id=len(hist) + 1, mission_id=mission_id, kind=kind, payload=payload)
        hist.append(event)
        for sink in self._sinks:
            await sink(event)
        cond = self._cond(mission_id)
        async with cond:
            cond.notify_all()
        if kind == EventKind.DONE:
            self._closed.add(mission_id)
        return event

    async def subscribe(self, mission_id: str, after_id: int = 0, poll_s: float = 15.0) -> AsyncIterator[Event]:
        """Yield events with id > after_id, then live events until the mission emits DONE."""
        cond = self._cond(mission_id)
        cursor = after_id
        while True:
            hist = self._history.get(mission_id, [])
            while cursor < len(hist):
                cursor += 1
                yield hist[cursor - 1]
            if mission_id in self._closed:
                return
            async with cond:
                try:
                    await asyncio.wait_for(cond.wait(), timeout=poll_s)
                except TimeoutError:
                    # Let the caller send a keep-alive comment.
                    yield Event(id=0, mission_id=mission_id, kind=EventKind.STATUS, payload={"keepalive": True})

    def forget(self, mission_id: str) -> None:
        self._history.pop(mission_id, None)
        self._conds.pop(mission_id, None)
        self._closed.discard(mission_id)
