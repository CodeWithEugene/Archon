"""SWE-bench catalog loading and repo-dir aware sandbox paths."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.models import MissionStatus
from app.core.router import Task
from app.missions.swe import SweCatalog, SweInstance
from app.sandbox.fake import FakeBackend
from app.sandbox.service import SandboxService


def test_catalog_loads_instance_files(tmp_path: Path) -> None:
    (tmp_path / "swe").mkdir()
    (tmp_path / "instances.json").write_text(json.dumps({"swe_bench_verified": ["psf__requests-1", "missing"]}))
    (tmp_path / "swe" / "psf__requests-1.json").write_text(
        json.dumps(
            {
                "id": "psf__requests-1",
                "repo": "https://github.com/psf/requests",
                "image": "swebench/sweb.eval.x86_64.psf_1776_requests-1:latest",
                "test_command": ". /opt/miniconda3/bin/activate testbed && pytest -q 'test_requests.py::T::t'",
                "fail_to_pass": ["test_requests.py::T::t"],
                "pass_to_pass": [],
                "test_patch": "diff --git a/x b/x\n",
                "problem_statement": "Something is wrong\nmore",
                "difficulty": "<15 min fix",
            }
        )
    )
    cat = SweCatalog.load(tmp_path / "instances.json")
    inst = cat.get("psf__requests-1")
    assert inst is not None and inst.workdir == "/testbed" and inst.fail_to_pass == ("test_requests.py::T::t",)
    assert cat.get("missing") is None
    assert cat.list()[0]["difficulty"] == "<15 min fix"


async def test_service_repo_dir_paths_and_prebuilt_patch() -> None:
    be = FakeBackend()
    svc = SandboxService(be, base_image_ref="x", command_timeout_s=60).with_repo_dir("/testbed")
    assert svc.repo_dir == "/testbed" and svc.patch_path == "/archon.patch" and svc.junit_path == "/archon-junit.xml"
    image = await svc.provision_prebuilt("swebench/img:latest", "diff --git a/t.py b/t.py\n", None)
    apply_call = be.calls[-1]
    assert apply_call.cwd == "/testbed" and "/archon.patch" in apply_call.files and "git apply" in apply_call.shell
    assert image in be.files and be.files[image]["/archon.patch"].startswith(b"diff --git")
    # no test patch -> no sandbox command
    n = len(be.calls)
    await svc.provision_prebuilt("swebench/img:latest", "", None)
    assert len(be.calls) == n
    default = SandboxService(be, base_image_ref="x", command_timeout_s=60)
    assert default.repo_dir == "/work/repo" and default.patch_path == "/work/archon.patch"


def _requests_like_instance() -> SweInstance:
    return SweInstance(
        id="acme__lib-1",
        repo="https://github.com/acme/lib",
        image="swebench/sweb.eval.x86_64.acme_1776_lib-1:latest",
        test_command="source /opt/miniconda3/bin/activate && conda activate testbed && pytest -q 'tests/test_a.py::test_x'",
        workdir="/testbed",
        test_patch="diff --git a/tests/test_a.py b/tests/test_a.py\n+++ b/tests/test_a.py\n",
        problem_statement="x() returns the wrong value",
        fail_to_pass=("tests/test_a.py::test_x",),
    )


async def test_swe_mission_reads_files_from_instance_workdir(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    """Regression: roles created before provisioning must read from /testbed, not /work/repo."""
    inst = _requests_like_instance()
    backend.default_files["/testbed/lib/core.py"] = b"def x():\n    return 1\n"
    backend.default_files["/testbed/tests/test_a.py"] = (
        b"from lib.core import x\n\ndef test_x():\n    assert x() == 2\n"
    )
    baseline = "FAILED tests/test_a.py::test_x - assert 1 == 2\n1 failed in 0.01s\n"
    fixed = "PASSED tests/test_a.py::test_x\n1 passed in 0.01s\n"
    backend.on(r"pytest", stdout=baseline, exit_code=1, once=True)
    backend.on(
        r"git add --",
        stdout="diff --git a/lib/core.py b/lib/core.py\n--- a/lib/core.py\n+++ b/lib/core.py\n@@ -1,2 +1,2 @@\n def x():\n-    return 1\n+    return 2\n",
    )
    backend.on(r"git ls-files", stdout="lib/core.py\ntests/test_a.py\n")
    backend.on(
        r"pytest",
        stdout=fixed,
        exit_code=0,
        when=lambda _s, f: f.get("/testbed/lib/core.py", b"").endswith(b"return 2\n"),
    )
    scripts = {
        Task.RESEARCH_QUERIES: [json.dumps({"queries": ["x returns wrong value"]})],
        Task.RESEARCH_BRIEF: [json.dumps({"brief": "n/a", "sources": []})],
        Task.DIAGNOSE_AND_PATCH: [
            json.dumps({"root_cause": "need source", "files_to_read": ["lib/core.py"], "candidates": []}),
            json.dumps(
                {
                    "root_cause": "off by one",
                    "files_to_read": [],
                    "candidates": [
                        {
                            "rationale": "fix",
                            "edits": [{"path": "lib/core.py", "search": "    return 1\n", "replace": "    return 2\n"}],
                        }
                    ],
                }
            ),
        ],
        Task.REVIEW: [json.dumps({"verdict": "APPROVE", "reasons": ["ok"]})],
    }
    runner, llm, _ = make_runner(scripts=scripts, swe=SweCatalog([inst]), swe_instance_id="acme__lib-1")
    m = await runner.run()
    assert m.status == MissionStatus.VERIFIED, m.failure_report
    second = [msgs for t, msgs in llm.calls if t == Task.DIAGNOSE_AND_PATCH][1][1]["content"]
    assert "source: lib/core.py" in second and "def x():" in second  # the read hit /testbed/lib/core.py
    assert "repository file list" in second and "issue description" in second
    # provisioning applied the instance test patch in /testbed
    assert any(c.cwd == "/testbed" and "/archon.patch" in c.files for c in backend.calls)
    assert m.summary["swe"]["instance"] == "acme__lib-1"


def test_resolve_path_suffix_and_basename() -> None:
    svc = SandboxService(FakeBackend(), base_image_ref="x", command_timeout_s=10)
    known = {"1.platform/server/app/x.py", "1.platform/server/tests/test_x.py", "README.md"}
    assert svc.resolve_path("platform/server/app/x.py", known) == "1.platform/server/app/x.py"
    assert svc.resolve_path("./1.platform/server/app/x.py", known) == "1.platform/server/app/x.py"
    assert svc.resolve_path("x.py", known) == "1.platform/server/app/x.py"  # unique basename
    assert svc.resolve_path("nope.py", known) == "nope.py"
    assert svc.resolve_path("/work/repo/README.md", known) == "README.md"


async def test_subdir_scopes_install_and_paths(make_runner, backend: FakeBackend) -> None:  # type: ignore[no-untyped-def]
    from app.core.models import Mission, MissionType, new_id

    backend.default_files["/work/repo/apps/svc/pyproject.toml"] = b"[project]"
    backend.default_files["/work/repo/apps/svc/svc/core.py"] = b"def x():\n    return 1\n"
    backend.on(
        r"pytest", stdout="FAILED tests/test_a.py::test_x - assert 1 == 2\n1 failed in 0.01s\n", exit_code=1, once=True
    )
    backend.on(r"git ls-files", stdout="svc/core.py\ntests/test_a.py\n")
    backend.on(
        r"git add --",
        stdout="diff --git a/apps/svc/svc/core.py b/apps/svc/svc/core.py\n--- a/apps/svc/svc/core.py\n+++ b/apps/svc/svc/core.py\n@@ -1,2 +1,2 @@\n def x():\n-    return 1\n+    return 2\n",
    )
    backend.on(
        r"pytest",
        stdout="PASSED tests/test_a.py::test_x\n1 passed in 0.01s\n",
        exit_code=0,
        when=lambda _s, f: f.get("/work/repo/apps/svc/svc/core.py", b"").endswith(b"return 2\n"),
    )
    scripts = {
        Task.RESEARCH_QUERIES: [json.dumps({"queries": ["q"]})],
        Task.RESEARCH_BRIEF: [json.dumps({"brief": "n/a", "sources": []})],
        Task.DIAGNOSE_AND_PATCH: [
            json.dumps(
                {
                    "root_cause": "r",
                    "files_to_read": [],
                    "candidates": [
                        {
                            "rationale": "fix",
                            "edits": [{"path": "svc/core.py", "search": "    return 1\n", "replace": "    return 2\n"}],
                        }
                    ],
                }
            )
        ],
        Task.REVIEW: [json.dumps({"verdict": "APPROVE", "reasons": ["ok"]})],
    }
    runner, _, _ = make_runner(scripts=scripts)
    runner.m = Mission(
        id=new_id("m"),
        type=MissionType.BUG_HEALING,
        repo_url="https://github.com/acme/mono",
        git_ref="main",
        test_command="pytest -q",
        swe_instance_id=None,
        subdir="apps/svc",
    )
    m = await runner.run()
    assert m.status == MissionStatus.VERIFIED, m.failure_report
    install = next(c for c in backend.calls if "pip install" in c.shell)
    assert install.cwd == "/work/repo/apps/svc"
    tests_run = [c for c in backend.calls if "pytest" in c.shell]
    assert all(c.cwd == "/work/repo/apps/svc" for c in tests_run)
    assert "/work/repo/apps/svc/svc/core.py" in next(c for c in backend.calls if "git add --" in c.shell).files
