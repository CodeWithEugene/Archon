"""Replays, SWE-bench catalog, pricing, and health."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import AppState, get_state
from app.observability import tracing

router = APIRouter(tags=["misc"])


@router.get("/healthz")
async def healthz(state: AppState = Depends(get_state)) -> dict[str, Any]:
    return {
        "ok": True,
        "env": state.settings.env,
        "sandbox_backend": state.sandbox_backend_name,
        "llm_backend": state.settings.llm_backend,
        "models": state.router.as_dict(),
        "live_mode_requires_token": state.settings.live_mode_requires_token,
        "running_missions": state.registry.running,
        "tracing": tracing.enabled(),
        "tracing_project": state.settings.langsmith_project if tracing.enabled() else None,
        "max_iterations": state.settings.max_iterations,
        "candidates_per_iteration": state.settings.candidates_per_iteration,
        "config_problems": state.settings.validate_for_runtime(),
    }


@router.get("/api/v1/replays")
async def list_replays(state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    return state.recorder.list()


@router.post("/api/v1/replays/{recording_id}/play", status_code=status.HTTP_202_ACCEPTED)
async def play_replay(recording_id: str, speed: float = 1.0, state: AppState = Depends(get_state)) -> dict[str, str]:
    replay = await state.recorder.start_replay(recording_id, speed=max(0.25, min(speed, 8.0)))
    if replay is None:
        raise HTTPException(status_code=404, detail="recording not found")
    return {"id": replay.id, "status": replay.status.value, "stream": f"/api/v1/missions/{replay.id}/events"}


@router.get("/api/v1/swe-instances")
async def swe_instances(state: AppState = Depends(get_state)) -> list[dict[str, str]]:
    return state.swe.list()


@router.get("/api/v1/pricing")
async def pricing(state: AppState = Depends(get_state)) -> dict[str, Any]:
    p = state.prices
    return {
        "updated": p.updated,
        "ratio": list(p.ratio),
        "sources": p.sources,
        "models": {k: v.__dict__ for k, v in p.models.items()},
        "migration_map": p.migration_map,
    }


@router.get("/api/v1/pricing/estimate")
async def estimate(
    source_model: str, monthly_tokens: int = 100_000_000, state: AppState = Depends(get_state)
) -> dict[str, Any]:
    est = state.prices.estimate(source_model, monthly_tokens=max(1, min(monthly_tokens, 10**12)))
    if est is None:
        raise HTTPException(status_code=404, detail="no price for that model")
    return est.__dict__
