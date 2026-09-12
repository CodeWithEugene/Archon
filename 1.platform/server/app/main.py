"""FastAPI application entry point. Wires settings, store, event bus, sandbox, models, and routes."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import events, misc, missions
from app.api.deps import AppState
from app.core.events import EventBus
from app.core.pricing import PriceTable
from app.core.registry import Registry
from app.core.router import ModelRouter, Task
from app.core.runner import LLMFactory
from app.grounding.tavily import DisabledGrounder, Grounder, TavilyGrounder
from app.llm.client import LLM, FakeLLM, NebiusLLM, UsageHook
from app.missions.swe import SweCatalog
from app.observability import tracing
from app.replay.recorder import Recorder
from app.sandbox.base import SandboxBackend
from app.sandbox.contree import ContreeBackend
from app.sandbox.fake import FakeBackend
from app.sandbox.local import LocalBackend
from app.sandbox.service import SandboxService
from app.settings import Settings, get_settings
from app.store.db import Store

logger = logging.getLogger("archon")


def build_sandbox_backend(settings: Settings) -> SandboxBackend:
    if settings.sandbox_backend == "contree":
        return ContreeBackend(
            token=settings.nebius_api_key,
            base_url=settings.nebius_sandbox_url,
            project_id=settings.nebius_project_id,
            operation_timeout_s=settings.command_timeout_s + 120,
        )
    if settings.sandbox_backend == "local":
        return LocalBackend(production=settings.env == "production")
    return FakeBackend()


def build_grounder(settings: Settings) -> Grounder:
    if settings.tavily_api_key:
        return TavilyGrounder(api_key=settings.tavily_api_key, timeout_s=settings.tavily_timeout_s)
    logger.warning("TAVILY_API_KEY not set; grounding disabled")
    return DisabledGrounder()


def build_llm_factory(settings: Settings, router: ModelRouter, prices: PriceTable) -> LLMFactory:
    if settings.llm_backend == "fake":

        def fake_factory(hook: UsageHook) -> LLM:
            llm = FakeLLM(router=router, usage_hook=hook)
            llm.push(Task.RESEARCH_QUERIES, '{"queries": ["example"]}')
            return llm

        return fake_factory

    def nebius_factory(hook: UsageHook) -> LLM:
        return NebiusLLM(
            api_key=settings.nebius_api_key,
            base_url=settings.nebius_base_url,
            router=router,
            prices=prices,
            usage_hook=hook,
        )

    return nebius_factory


def build_state(settings: Settings, store: Store, bus: EventBus, backend: SandboxBackend) -> AppState:
    prices = PriceTable.load(settings.pricing_path)
    router = ModelRouter(settings)
    sandbox = SandboxService(backend, base_image_ref=settings.base_image, command_timeout_s=settings.command_timeout_s)
    recorder = Recorder(settings.recordings_dir, store, bus)
    return AppState(
        settings=settings,
        store=store,
        bus=bus,
        prices=prices,
        router=router,
        sandbox=sandbox,
        grounder=build_grounder(settings),
        llm_factory=build_llm_factory(settings, router, prices),
        registry=Registry(),
        recorder=recorder,
        swe=SweCatalog.load(settings.swe_instances_path),
        sandbox_backend_name=backend.name,
    )


def create_app(settings: Settings | None = None, backend: SandboxBackend | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for problem in settings.validate_for_runtime():
        logger.warning("config: %s", problem)
    tracing.configure(settings.langsmith_api_key, settings.langsmith_project, settings.langsmith_endpoint or None)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store = Store(settings.db_path)
        await store.open()
        bus = EventBus()
        bus.add_sink(store.save_event)
        sb = backend or build_sandbox_backend(settings)
        app.state.archon = build_state(settings, store, bus, sb)
        logger.info(
            "ARCHON up: sandbox=%s llm=%s models=%s",
            sb.name,
            settings.llm_backend,
            app.state.archon.router.as_dict(),
        )
        try:
            yield
        finally:
            await app.state.archon.registry.shutdown()
            await sb.close()
            await store.close()

    app = FastAPI(title="ARCHON", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
    )
    app.include_router(missions.router)
    app.include_router(events.router)
    app.include_router(misc.router)
    return app


app = create_app()
