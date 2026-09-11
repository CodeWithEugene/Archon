"""The development-only local backend: fork isolation, file mapping, timeout, and a real fixture run."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.sandbox.base import RunSpec, SandboxError
from app.sandbox.local import LocalBackend
from app.sandbox.service import SandboxService
from tests.golden.local_repos import materialize

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None, reason="needs bash and git"
)


async def test_fork_isolation_and_files(tmp_path: Path) -> None:
    be = LocalBackend(root=tmp_path / "imgs")
    base = await be.base_image("python:3.12")
    a = await be.run(base, RunSpec(shell="echo hello > x.txt && cat x.txt", cwd="/work"))
    assert a.exit_code == 0 and "hello" in a.stdout and a.image_id
    # sibling fork of base must not see x.txt
    b = await be.run(base, RunSpec(shell="cat x.txt", cwd="/work"))
    assert b.exit_code != 0
    # files are placed relative to the image root
    c = await be.run(base, RunSpec(shell="cat archon.patch", cwd="/work", files={"/work/archon.patch": b"PATCH"}))
    assert c.stdout.strip() == "PATCH"
    assert await be.read_file(a.image_id, "/work/x.txt") == b"hello\n"
    with pytest.raises(FileNotFoundError):
        await be.read_file(a.image_id, "/work/nope")
    with pytest.raises(SandboxError):
        await be.read_file(a.image_id, "/../../etc/passwd")
    await be.close()


async def test_timeout(tmp_path: Path) -> None:
    be = LocalBackend(root=tmp_path / "imgs")
    base = await be.base_image("x")
    r = await be.run(base, RunSpec(shell="sleep 5", timeout_s=1))
    assert r.timed_out and r.exit_code == 124
    await be.close()


def test_refuses_production(tmp_path: Path) -> None:
    with pytest.raises(SandboxError):
        LocalBackend(root=tmp_path, production=True)


@pytest.mark.slow
async def test_fixture_baseline_and_solution_patch(tmp_path: Path) -> None:
    """Real end-to-end sandbox behaviour on the broken_pydantic_v2 fixture, no model involved."""
    if shutil.which("python3") is None:
        pytest.skip("python3 missing")
    url = materialize("broken_pydantic_v2", tmp_path / "repos")
    be = LocalBackend(root=tmp_path / "imgs")
    svc = SandboxService(be, base_image_ref="x", command_timeout_s=600)
    lines: list[str] = []

    async def hook(stream: str, line: str) -> None:
        lines.append(f"{stream}: {line}")

    image = await svc.provision_repo(
        url, "main", "python3 -m venv .venv && . .venv/bin/activate && pip install -q -e . pytest", hook
    )
    base = await svc.baseline(image, ". .venv/bin/activate && pytest -q", hook)
    assert base.report.exit_code != 0
    assert len(base.report.failing) == 4 and len(base.report.passed) == 2, base.report
    solution = await svc.read_repo_file(image, "solution.patch")
    assert solution
    run = await svc.try_patch(image, solution, ". .venv/bin/activate && pytest -q", hook)
    assert run.applied and run.report is not None
    assert run.report.exit_code == 0 and len(run.report.passed) == 6
    # baseline image untouched
    again = await svc.baseline(image, ". .venv/bin/activate && pytest -q", None)
    assert again.report.exit_code != 0
    await be.close()
