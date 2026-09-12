"""Shared fixtures: fake sandbox, fake LLM, in-memory-ish store, and a runner factory."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from app.core.events import EventBus
from app.core.models import Mission, MissionType, new_id
from app.core.pricing import PriceTable
from app.core.router import ModelRouter, Task
from app.core.runner import MissionRunner, RunnerDeps
from app.grounding.tavily import FakeGrounder, SearchHit
from app.llm.client import FakeLLM, UsageHook
from app.missions.swe import SweCatalog
from app.sandbox.fake import FakeBackend
from app.sandbox.service import SandboxService
from app.settings import Settings
from app.store.db import Store

SERVER_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True, scope="session")
def _no_langsmith_uploads() -> None:  # type: ignore[misc]
    """Unit tests must never reach LangSmith, whatever the developer's shell or .env contains."""
    import os

    for key in ("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY", "LANGCHAIN_TRACING_V2"):
        os.environ.pop(key, None)
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGSMITH_ENDPOINT"] = "http://127.0.0.1:9"  # unroutable, belt and braces


BASELINE_FAIL = """============================= test session starts ==============================
collected 3 items

tests/test_app.py::test_a FAILED
tests/test_app.py::test_b PASSED
tests/test_app.py::test_c PASSED

=================================== FAILURES ===================================
___________________________________ test_a _____________________________________
  File "/work/repo/app/core.py", line 3, in add
    return a + b + c
NameError: name 'c' is not defined
=========================== short test summary info ============================
FAILED tests/test_app.py::test_a - NameError: name 'c' is not defined
PASSED tests/test_app.py::test_b
PASSED tests/test_app.py::test_c
========================= 1 failed, 2 passed in 0.10s ==========================
"""

ALL_PASS = """============================= test session starts ==============================
collected 3 items
=========================== short test summary info ============================
PASSED tests/test_app.py::test_a
PASSED tests/test_app.py::test_b
PASSED tests/test_app.py::test_c
============================== 3 passed in 0.05s ===============================
"""

REGRESSION = """=========================== short test summary info ============================
PASSED tests/test_app.py::test_a
FAILED tests/test_app.py::test_b - AssertionError
PASSED tests/test_app.py::test_c
========================= 1 failed, 2 passed in 0.05s ==========================
"""

GOOD_PATCH = """diff --git a/app/core.py b/app/core.py
--- a/app/core.py
+++ b/app/core.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a + b + c
+    return a + b
"""

BAD_PATCH = """diff --git a/app/core.py b/app/core.py
--- a/app/core.py
+++ b/app/core.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a + b + c
+    return a - b
"""

ORIGINAL_CORE = b"def add(a, b):\n    return a + b + c\n"


def engineer_json(*patches: str, root_cause: str = "c is undefined") -> str:
    return json.dumps(
        {
            "root_cause": root_cause,
            "files_to_read": [],
            "candidates": [{"rationale": f"candidate {i}", "patch": p} for i, p in enumerate(patches)],
        }
    )


def approve() -> str:
    return json.dumps({"verdict": "APPROVE", "reasons": ["minimal and related"]})


def reject(*reasons: str) -> str:
    return json.dumps({"verdict": "REJECT", "reasons": list(reasons) or ["unrelated change"]})


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        NEBIUS_API_KEY="",
        ARCHON_LLM_BACKEND="fake",
        ARCHON_SANDBOX_BACKEND="fake",
        ARCHON_DB_PATH=tmp_path / "t.db",
        ARCHON_RECORDINGS_DIR=tmp_path / "rec",
        ARCHON_PRICING_PATH=SERVER_ROOT / "pricing.json",
        ARCHON_SWE_INSTANCES=tmp_path / "missing.json",
        ARCHON_MAX_MISSION_USD=3.0,
        ARCHON_MAX_ITERATIONS=3,
        ARCHON_CANDIDATES_PER_ITERATION=2,
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def prices(settings: Settings) -> PriceTable:
    return PriceTable.load(settings.pricing_path)


@pytest.fixture
def router(settings: Settings) -> ModelRouter:
    return ModelRouter(settings)


@pytest.fixture
async def store(settings: Settings) -> AsyncIterator[Store]:
    s = Store(settings.db_path)
    await s.open()
    yield s
    await s.close()


@pytest.fixture
def bus(store: Store) -> EventBus:
    b = EventBus()
    b.add_sink(store.save_event)
    return b


@pytest.fixture
def backend() -> FakeBackend:
    fb = FakeBackend(default_files={"/work/repo/app/core.py": ORIGINAL_CORE, "/work/repo/pyproject.toml": b"[project]"})
    fb.on(r"git clone", stdout="abc123 fixture")
    fb.on(r"pip install", stdout="ok")
    return fb


def good_applied(_shell: str, files: dict[str, bytes]) -> bool:
    return b"return a + b\n" in files.get("/work/archon.patch", b"")


def bad_applied(_shell: str, files: dict[str, bytes]) -> bool:
    return b"return a - b" in files.get("/work/archon.patch", b"")


@pytest.fixture
def make_runner(
    settings: Settings, store: Store, bus: EventBus, backend: FakeBackend, prices: PriceTable, router: ModelRouter
) -> Callable[..., tuple[MissionRunner, FakeLLM, FakeGrounder]]:
    def _make(
        *,
        mission_type: MissionType = MissionType.BUG_HEALING,
        scripts: dict[Task, list[str]] | None = None,
        cost_per_call: float = 0.01,
        grounder_hits: bool = True,
        settings_override: Settings | None = None,
        swe: SweCatalog | None = None,
        swe_instance_id: str | None = None,
    ) -> tuple[MissionRunner, FakeLLM, FakeGrounder]:
        s = settings_override or settings
        holder: dict[str, FakeLLM] = {}

        def factory(hook: UsageHook) -> FakeLLM:
            llm = FakeLLM(scripts=scripts, router=router, usage_hook=hook, cost_per_call=cost_per_call)
            holder["llm"] = llm
            return llm

        grounder = FakeGrounder(
            hits=[SearchHit(title="Changelog", url="https://example.org/cl", content="c was removed in 2.0")]
            if grounder_hits
            else [],
        )
        mission = Mission(
            id=new_id("m"),
            type=mission_type,
            repo_url=None if swe_instance_id else "https://github.com/acme/demo",
            git_ref="main",
            test_command=None if swe_instance_id else "pytest -q",
            swe_instance_id=swe_instance_id,
        )
        deps = RunnerDeps(
            store=store,
            bus=bus,
            sandbox=SandboxService(backend, base_image_ref="python:3.12-slim", command_timeout_s=60),
            llm_factory=factory,
            grounder=grounder,
            prices=prices,
            settings=s,
            swe=swe or SweCatalog([]),
        )
        runner = MissionRunner(mission, deps)
        return runner, holder["llm"], grounder

    return _make
