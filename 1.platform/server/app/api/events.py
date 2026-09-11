"""Server-Sent Events stream for a mission."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.deps import AppState, get_state

router = APIRouter(prefix="/api/v1/missions", tags=["events"])


def _frame(event_id: int, kind: str, payload: dict[str, object]) -> str:
    return f"id: {event_id}\nevent: {kind}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


@router.get("/{mission_id}/events")
async def mission_events(
    mission_id: str,
    request: Request,
    state: AppState = Depends(get_state),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    mission = await state.store.get_mission(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission not found")
    after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def gen() -> AsyncIterator[str]:
        yield ": archon stream\n\n"
        # Events that finished before this subscriber existed come from the store.
        if not state.bus.history(mission_id):
            for e in await state.store.events(mission_id):
                if e.id > after:
                    yield _frame(e.id, e.kind.value, e.payload)
                    if e.kind.value == "done":
                        return
            if mission.status.terminal:
                return
        async for e in state.bus.subscribe(mission_id, after_id=after):
            if await request.is_disconnected():
                return
            if e.id == 0:
                yield ": keepalive\n\n"
                continue
            yield _frame(e.id, e.kind.value, e.payload)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
