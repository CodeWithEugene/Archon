"""FastAPI dependencies: app state access and live-mode authorization."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from app.core.events import EventBus
from app.core.pricing import PriceTable
from app.core.registry import Registry
from app.core.router import ModelRouter
from app.core.runner import LLMFactory
from app.grounding.tavily import Grounder
from app.missions.swe import SweCatalog
from app.replay.recorder import Recorder
from app.sandbox.service import SandboxService
from app.settings import Settings
from app.store.db import Store


@dataclass
class AppState:
    settings: Settings
    store: Store
    bus: EventBus
    prices: PriceTable
    router: ModelRouter
    sandbox: SandboxService
    grounder: Grounder
    llm_factory: LLMFactory
    registry: Registry
    recorder: Recorder
    swe: SweCatalog
    sandbox_backend_name: str


def get_state(request: Request) -> AppState:
    state = getattr(request.app.state, "archon", None)
    if state is None:
        raise HTTPException(status_code=503, detail="server not initialised")
    assert isinstance(state, AppState)
    return state


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_live_access(request: Request, state: AppState = Depends(get_state)) -> None:
    """Live missions spend credits. Require the demo token when one is configured, and rate-limit by IP."""
    if state.settings.live_mode_requires_token:
        auth = request.headers.get("authorization", "")
        token = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else ""
        if not token or token != state.settings.demo_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="live mode requires a valid demo token"
            )
    if not state.registry.allow_live(client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many live missions; try a replay or wait",
        )
