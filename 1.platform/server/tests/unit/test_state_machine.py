"""End-to-end runner behaviour against the fake sandbox and fake LLM."""

from __future__ import annotations

import json

from app.core.models import EventKind, MissionStatus, MissionType
from app.core.router import Task
from app.sandbox.fake import FakeBackend
from tests.unit.conftest import (
    ALL_PASS,
    BAD_PATCH,
    BASELINE_FAIL,
    GOOD_PATCH,
    REGRESSION,
    approve,
    bad_applied,
    engineer_json,
    good_applied,
    reject,
)


def research_scripts() -> dict[Task, list[str]]:
    return {
        Task.RESEARCH_QUERIES: [json.dumps({"queries": ["NameError c is not defined", "lib 2.0 changelog"]})],
        Task.RESEARCH_BRIEF: [
            json.dumps({"brief": "c was removed in 2.0; drop it.", "sources": ["https://example.org/cl"]})
        ],
    }


def kinds(bus_history: list) -> list[str]:  # type: ignore[type-arg]
    return [e.kind.value for e in bus_history]


async def test_nothing_to_fix_when_baseline_green(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=ALL_PASS, exit_code=0)
    runner, llm, _ = make_runner(scripts={})
    m = await runner.run()
    assert m.status == MissionStatus.NOTHING_TO_FIX
    assert llm.calls == []  # no model spend when there is nothing to do
    hist = runner.d.bus.history(m.id)
    assert hist[-1].kind == EventKind.DONE
    assert any(e.kind == EventKind.TERMINAL and e.payload["attempt"] == "baseline" for e in hist)


async def test_resolves_in_one_iteration_with_best_of_two(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1, once=True)
    backend.on(r"pytest", stdout=ALL_PASS, exit_code=0, when=good_applied)
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1, when=bad_applied)
    scripts = research_scripts()
    scripts[Task.DIAGNOSE_AND_PATCH] = [engineer_json(BAD_PATCH, GOOD_PATCH)]
    scripts[Task.REVIEW] = [approve()]
    runner, llm, grounder = make_runner(scripts=scripts)
    m = await runner.run()

    assert m.status == MissionStatus.VERIFIED
    assert m.iteration == 1
    assert grounder.queries == ["NameError c is not defined", "lib 2.0 changelog"]
    attempts = await runner.d.store.attempts(m.id)
    assert len(attempts) == 2
    selected = [a for a in attempts if a.selected]
    assert len(selected) == 1 and selected[0].patch == GOOD_PATCH
    assert selected[0].fail_to_pass == 1 and selected[0].pass_to_pass_broken == 0
    assert m.diff and m.diff[0].path == "app/core.py"
    assert m.diff[0].original.startswith("def add")
    hist = runner.d.bus.history(m.id)
    assert "tavily" in kinds(hist) and "review" in kinds(hist) and "usage" in kinds(hist)
    assert hist[-1].payload["status"] == "VERIFIED"
    # Ultra was called exactly once, Super for research and review.
    ultra_calls = [t for t, _ in llm.calls if t == Task.DIAGNOSE_AND_PATCH]
    assert len(ultra_calls) == 1


async def test_regression_is_never_selected(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1, once=True)
    backend.on(r"pytest", stdout=REGRESSION, exit_code=1, when=good_applied)  # fixes a, breaks b
    scripts = research_scripts()
    scripts[Task.DIAGNOSE_AND_PATCH] = [engineer_json(GOOD_PATCH)] * 3
    runner, _, _ = make_runner(scripts=scripts, grounder_hits=True)
    m = await runner.run()
    assert m.status == MissionStatus.FAILED
    assert m.iteration == 3
    attempts = await runner.d.store.attempts(m.id)
    assert all(a.pass_to_pass_broken == 1 for a in attempts)
    assert not any(a.selected for a in attempts)


async def test_fails_after_iteration_limit(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1)
    scripts = research_scripts()
    scripts[Task.DIAGNOSE_AND_PATCH] = [engineer_json(BAD_PATCH)] * 3
    runner, llm, _ = make_runner(scripts=scripts)
    m = await runner.run()
    assert m.status == MissionStatus.FAILED
    assert m.iteration == 3
    assert "3 iterations" in (m.failure_report or "")
    # Second iteration received the previous attempt in its prompt.
    second = [msgs for t, msgs in llm.calls if t == Task.DIAGNOSE_AND_PATCH][1]
    assert "previous attempt" in second[1]["content"]


async def test_reviewer_reject_then_approve(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1, once=True)
    backend.on(r"pytest", stdout=ALL_PASS, exit_code=0, when=good_applied)
    scripts = research_scripts()
    scripts[Task.DIAGNOSE_AND_PATCH] = [engineer_json(GOOD_PATCH), engineer_json(GOOD_PATCH)]
    scripts[Task.REVIEW] = [reject("touches unrelated code"), approve()]
    runner, _, _ = make_runner(scripts=scripts)
    m = await runner.run()
    assert m.status == MissionStatus.VERIFIED
    assert m.iteration == 2
    reviews = [e for e in runner.d.bus.history(m.id) if e.kind == EventKind.REVIEW]
    assert [r.payload["verdict"] for r in reviews] == ["REJECT", "APPROVE"]


async def test_spend_cap_aborts(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1)
    scripts = research_scripts()
    scripts[Task.DIAGNOSE_AND_PATCH] = [engineer_json(BAD_PATCH)] * 3
    runner, _, _ = make_runner(scripts=scripts, cost_per_call=1.6)  # cap is 3.0 -> second call trips it
    m = await runner.run()
    assert m.status == MissionStatus.ABORTED
    assert "spend cap" in (m.failure_report or "")
    assert m.spend_usd >= 3.0


async def test_user_abort(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1)
    runner, _, _ = make_runner(scripts=research_scripts())
    runner.abort("user clicked stop")
    m = await runner.run()
    assert m.status == MissionStatus.ABORTED
    assert m.failure_report == "user clicked stop"


async def test_unsafe_patch_rejected_before_execution(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1)
    evil = GOOD_PATCH.replace("+    return a + b\n", '+    API_KEY = "sk-' + "a" * 30 + '"\n+    return a + b\n')
    scripts = research_scripts()
    scripts[Task.DIAGNOSE_AND_PATCH] = [engineer_json(evil)] * 3
    runner, _, _ = make_runner(scripts=scripts)
    m = await runner.run()
    assert m.status == MissionStatus.FAILED
    attempts = await runner.d.store.attempts(m.id)
    assert all(not a.applied and a.error and "credential" in a.error for a in attempts)
    assert not any("git apply" in c.shell for c in backend.calls)


async def test_git_apply_failure_feeds_next_iteration(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1, once=True)
    backend.on(r"git apply --check", exit_code=1, stderr="error: patch failed: app/core.py:1", once=True)
    backend.on(r"pytest", stdout=ALL_PASS, exit_code=0, when=good_applied)
    scripts = research_scripts()
    scripts[Task.DIAGNOSE_AND_PATCH] = [engineer_json(GOOD_PATCH), engineer_json(GOOD_PATCH)]
    scripts[Task.REVIEW] = [approve()]
    runner, _, _ = make_runner(scripts=scripts)
    m = await runner.run()
    assert m.status == MissionStatus.VERIFIED
    assert m.iteration == 2


async def test_engineer_reads_more_files_then_patches(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1, once=True)
    backend.on(r"pytest", stdout=ALL_PASS, exit_code=0, when=good_applied)
    backend.default_files["/work/repo/app/other.py"] = b"X = 1\n"
    scripts = research_scripts()
    scripts[Task.DIAGNOSE_AND_PATCH] = [
        json.dumps({"root_cause": "need more", "files_to_read": ["app/other.py"], "candidates": []}),
        engineer_json(GOOD_PATCH),
    ]
    scripts[Task.REVIEW] = [approve()]
    runner, llm, _ = make_runner(scripts=scripts)
    m = await runner.run()
    assert m.status == MissionStatus.VERIFIED
    second = [msgs for t, msgs in llm.calls if t == Task.DIAGNOSE_AND_PATCH][1]
    assert "source: app/other.py" in second[1]["content"]


async def test_grounding_failure_does_not_block(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1, once=True)
    backend.on(r"pytest", stdout=ALL_PASS, exit_code=0, when=good_applied)
    scripts = {
        Task.RESEARCH_QUERIES: [json.dumps({"queries": ["q"]})],
        Task.DIAGNOSE_AND_PATCH: [engineer_json(GOOD_PATCH)],
        Task.REVIEW: [approve()],
    }
    runner, _, _ = make_runner(scripts=scripts, grounder_hits=False)
    m = await runner.run()
    assert m.status == MissionStatus.VERIFIED
    thoughts = [e.payload["text"] for e in runner.d.bus.history(m.id) if e.kind == EventKind.THOUGHT]
    assert any("without web grounding" in t for t in thoughts)


async def test_migration_mission(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.default_files["/work/repo/svc/client.py"] = (
        b'from openai import OpenAI\nclient = OpenAI()\nMODEL = "gpt-5.4"\n'
    )
    backend.on(r"pytest", stdout=ALL_PASS, exit_code=0)
    backend.on(r"rg -n", stdout='./svc/client.py:1:from openai import OpenAI\n./svc/client.py:3:MODEL = "gpt-5.4"\n')
    mig_patch = """diff --git a/svc/client.py b/svc/client.py
--- a/svc/client.py
+++ b/svc/client.py
@@ -1,3 +1,4 @@
+import os
 from openai import OpenAI
-client = OpenAI()
-MODEL = "gpt-5.4"
+client = OpenAI(base_url=os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"), api_key=os.environ["NEBIUS_API_KEY"])
+MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b"
"""
    scripts = {
        Task.MIGRATE: [engineer_json(mig_patch, root_cause="migrated client and model")],
        Task.REVIEW: [approve()],
    }
    runner, llm, grounder = make_runner(mission_type=MissionType.MIGRATION, scripts=scripts)
    m = await runner.run()
    assert m.status == MissionStatus.VERIFIED
    assert grounder.queries == []  # migration does not web-search
    scan = m.summary["migration_scan"]
    assert scan["mapping"] == {"gpt-5.4": "nvidia/Nemotron-3-Ultra-550b-a55b"}
    assert scan["estimates"][0]["reduction_pct"] > 50
    mig_call = [msgs for t, msgs in llm.calls if t == Task.MIGRATE][0]
    assert "gpt-5.4 -> nvidia/Nemotron-3-Ultra-550b-a55b" in mig_call[1]["content"]
    assert "source: svc/client.py" in mig_call[1]["content"]


async def test_migration_requires_green_baseline(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    backend.on(r"pytest", stdout=BASELINE_FAIL, exit_code=1)
    runner, llm, _ = make_runner(mission_type=MissionType.MIGRATION, scripts={})
    m = await runner.run()
    assert m.status == MissionStatus.FAILED
    assert "green baseline" in (m.failure_report or "")
    assert llm.calls == []
