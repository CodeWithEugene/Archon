"""Golden-dataset runner.

Runs missions end to end and records them for replay mode.

Examples:
  # Smoke: local backend, scripted model (uses the fixture's solution.patch), no credits spent
  python -m tests.golden.run --fixture broken_pydantic_v2 --llm fake --backend local --record

  # Real: local backend, live Nemotron on Nebius
  NEBIUS_API_KEY=... TAVILY_API_KEY=... python -m tests.golden.run --fixture broken_pydantic_v2 --llm nebius --backend local --record

  # Real: Token Factory Sandboxes
  NEBIUS_API_KEY=... NEBIUS_PROJECT_ID=... python -m tests.golden.run --swe <instance-id> --llm nebius --backend contree --record
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from app.core.events import EventBus
from app.core.models import Event, EventKind, Mission, MissionType, new_id
from app.core.pricing import PriceTable
from app.core.router import ModelRouter, Task
from app.core.runner import MissionRunner, RunnerDeps
from app.llm.client import FakeLLM, UsageHook
from app.main import build_grounder, build_llm_factory, build_sandbox_backend
from app.missions.swe import SweCatalog
from app.observability import tracing
from app.replay.recorder import Recorder
from app.sandbox.service import SandboxService
from app.settings import Settings
from app.store.db import Store
from tests.golden.local_repos import FIXTURES, materialize

FIXTURE_COMMANDS: dict[str, tuple[MissionType, str, str]] = {
    # name: (type, install, test)
    "broken_pydantic_v2": (
        MissionType.BUG_HEALING,
        "python3 -m venv .venv && . .venv/bin/activate && pip install -q -e . pytest",
        ". .venv/bin/activate && pytest -q",
    ),
    "openai_chat_service": (
        MissionType.MIGRATION,
        "python3 -m venv .venv && . .venv/bin/activate && pip install -q -e . pytest",
        ". .venv/bin/activate && pytest -q",
    ),
    "anthropic_summarizer": (
        MissionType.MIGRATION,
        "python3 -m venv .venv && . .venv/bin/activate && pip install -q -e . pytest",
        ". .venv/bin/activate && pytest -q",
    ),
}
SANDBOX_INSTALL = "python -m pip install -q -e . pytest"
SANDBOX_TEST = "pytest -q"


def scripted_llm_factory(router: ModelRouter, fixture: str) -> tuple[object, object]:
    """A FakeLLM that answers with the fixture's reference patch. Proves the loop without spending credits."""
    solution = (FIXTURES / fixture / "solution.patch").read_text(encoding="utf-8")

    def factory(hook: UsageHook) -> FakeLLM:
        llm = FakeLLM(router=router, usage_hook=hook, cost_per_call=0.0)
        llm.push(Task.RESEARCH_QUERIES, json.dumps({"queries": ["pydantic v2 validator migration field_validator"]}))
        llm.push(
            Task.RESEARCH_BRIEF,
            json.dumps(
                {
                    "brief": "Pydantic 2 replaced @validator with @field_validator and Config with model_config.",
                    "sources": [],
                }
            ),
        )
        engineer = json.dumps(
            {
                "root_cause": "The models use Pydantic v1 APIs that Pydantic 2 deprecates or rejects.",
                "files_to_read": [],
                "candidates": [{"rationale": "reference solution", "patch": solution}],
            }
        )
        llm.push(Task.DIAGNOSE_AND_PATCH, engineer)
        llm.push(Task.MIGRATE, engineer)
        llm.push(Task.REVIEW, json.dumps({"verdict": "APPROVE", "reasons": ["matches reference"]}))
        return llm

    return factory, None


def print_event(e: Event) -> None:
    p = e.payload
    if e.kind == EventKind.TERMINAL:
        print(f"  [{p.get('attempt')}] {p.get('line')}")
    elif e.kind == EventKind.THOUGHT:
        print(f"* {p.get('stage')}: {str(p.get('text'))[:300]}")
    elif e.kind == EventKind.STATUS:
        print(f"== {p.get('status')} (iteration {p.get('iteration')})")
    elif e.kind == EventKind.TESTS:
        print(
            f"  tests[{p.get('attempt')}]: exit={p.get('exit_code')} passed={p.get('passed')} failed={p.get('failed')} f2p={p.get('fail_to_pass')} broken={p.get('pass_to_pass_broken')}"
        )
    elif e.kind in {
        EventKind.TAVILY,
        EventKind.REVIEW,
        EventKind.ERROR,
        EventKind.DONE,
        EventKind.USAGE,
        EventKind.PATCH,
    }:
        print(f"  {e.kind.value}: {json.dumps(p)[:400]}")


async def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixture", choices=sorted(FIXTURE_COMMANDS), help="local fixture to run")
    ap.add_argument("--swe", help="SWE-bench Verified instance id from tests/golden/instances.json")
    ap.add_argument("--repo", help="public GitHub URL")
    ap.add_argument("--test-command", default=None)
    ap.add_argument("--install-command", default=None)
    ap.add_argument("--subdir", default=None, help="subproject path inside the repository")
    ap.add_argument("--type", choices=[t.value for t in MissionType], default=None)
    ap.add_argument("--llm", choices=["fake", "nebius"], default="nebius")
    ap.add_argument("--backend", choices=["local", "contree"], default="local")
    ap.add_argument("--record", action="store_true", help="write the recording to ARCHON_RECORDINGS_DIR")
    ap.add_argument("--db", default="./golden.db")
    args = ap.parse_args(argv)

    if not (args.fixture or args.swe or args.repo):
        ap.error("one of --fixture, --swe, --repo is required")

    settings = Settings(
        ARCHON_LLM_BACKEND=args.llm,
        ARCHON_SANDBOX_BACKEND=args.backend,
        ARCHON_DB_PATH=Path(args.db),
        ARCHON_ALLOW_LOCAL_REPOS=True,
    )  # type: ignore[call-arg]
    problems = settings.validate_for_runtime()
    if problems and args.llm != "fake":
        print("config problems:", *problems, sep="\n  ")
        return 2

    if tracing.configure(settings.langsmith_api_key, settings.langsmith_project, settings.langsmith_endpoint or None):
        print(f"tracing -> LangSmith project {settings.langsmith_project!r}")
    store = Store(settings.db_path)
    await store.open()
    bus = EventBus()
    bus.add_sink(store.save_event)

    async def printer(e: Event) -> None:
        print_event(e)

    bus.add_sink(printer)
    prices = PriceTable.load(settings.pricing_path)
    router = ModelRouter(settings)
    backend = build_sandbox_backend(settings)
    sandbox = SandboxService(backend, base_image_ref=settings.base_image, command_timeout_s=settings.command_timeout_s)
    recorder = Recorder(settings.recordings_dir, store, bus)
    swe = SweCatalog.load(settings.swe_instances_path)

    if args.fixture:
        mtype, install, test = FIXTURE_COMMANDS[args.fixture]
        if args.backend == "contree":
            install, test = SANDBOX_INSTALL, SANDBOX_TEST
        repo_url = materialize(args.fixture) if args.backend == "local" else None
        if repo_url is None:
            print("fixtures run only with --backend local; push the fixture to GitHub and use --repo for sandboxes")
            return 2
        mission = Mission(
            id=new_id("m"),
            type=mtype,
            repo_url=repo_url,
            git_ref="main",
            test_command=test,
            install_command=install,
            swe_instance_id=None,
        )
    elif args.swe:
        mission = Mission(
            id=new_id("m"),
            type=MissionType.BUG_HEALING,
            repo_url=None,
            git_ref="main",
            test_command=None,
            swe_instance_id=args.swe,
        )
    else:
        mission = Mission(
            id=new_id("m"),
            type=MissionType(args.type or "BUG_HEALING"),
            repo_url=args.repo,
            git_ref="main",
            test_command=args.test_command or "pytest -q",
            install_command=args.install_command,
            swe_instance_id=None,
            subdir=args.subdir,
        )

    if args.llm == "fake":
        if not args.fixture:
            print("--llm fake needs --fixture (it replays the fixture's solution.patch)")
            return 2
        llm_factory, _ = scripted_llm_factory(router, args.fixture)
    else:
        llm_factory = build_llm_factory(settings, router, prices)

    async def on_finished(m: Mission) -> None:
        if args.record:
            path = await recorder.record(m)
            print(f"recorded -> {path}")

    deps = RunnerDeps(
        store=store,
        bus=bus,
        sandbox=sandbox,
        llm_factory=llm_factory,
        grounder=build_grounder(settings),
        prices=prices,
        settings=settings,
        swe=swe,
        on_finished=on_finished,
    )  # type: ignore[arg-type]
    await store.save_mission(mission)
    print(
        f"mission {mission.id}: {mission.type.value} {mission.repo_url or mission.swe_instance_id} backend={backend.name} llm={args.llm}"
    )
    t0 = time.monotonic()
    result = await MissionRunner(mission, deps).run()
    print(
        f"\nRESULT: {result.status.value} in {time.monotonic() - t0:.1f}s, iterations={result.iteration}, spend=${result.spend_usd:.4f}"
    )
    if result.failure_report:
        print("failure report:", result.failure_report[:2000])
    if result.diff:
        print("changed files:", [d.path for d in result.diff])
    await backend.close()
    await store.close()
    return 0 if result.status.value == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
