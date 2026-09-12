"""High-level sandbox operations used by the mission runner. Backend-agnostic."""

from __future__ import annotations

import shlex
from dataclasses import dataclass

from app.core.models import TestReport
from app.observability.tracing import traced
from app.sandbox.base import REPO_DIR, WORKDIR, OutputHook, RunResult, RunSpec, SandboxBackend, SandboxError
from app.sandbox.pytest_parser import JUNIT_ABSOLUTE, ensure_pytest_flags, parse_junit, parse_pytest

PATCH_PATH = f"{WORKDIR}/archon.patch"
MAX_EXCERPT_BYTES = 60_000


@dataclass
class Baseline:
    image_id: str
    report: TestReport
    output: str


@dataclass
class AttemptRun:
    image_id: str | None
    applied: bool
    report: TestReport | None
    output: str
    exit_code: int


class SandboxService:
    def __init__(self, backend: SandboxBackend, *, base_image_ref: str, command_timeout_s: int) -> None:
        self.backend = backend
        self.base_image_ref = base_image_ref
        self.timeout = command_timeout_s

    # ---- provisioning -------------------------------------------------------------------------

    @traced("sandbox.provision_repo", run_type="tool")
    async def provision_repo(
        self,
        repo_url: str,
        git_ref: str,
        install_command: str | None,
        on_output: OutputHook | None,
    ) -> str:
        base = await self.backend.base_image(self.base_image_ref)
        clone = (
            f"git clone --quiet --depth 200 {shlex.quote(repo_url)} repo && cd repo && "
            f"git checkout --quiet {shlex.quote(git_ref)} && git log --oneline -1"
        )
        res = await self.backend.run(base, RunSpec(shell=clone, timeout_s=min(self.timeout, 600)), on_output)
        if res.exit_code != 0 or res.image_id is None:
            raise SandboxError("git clone or checkout failed", res)
        install = install_command or await self._detect_install(res.image_id)
        res2 = await self.backend.run(
            res.image_id, RunSpec(shell=install, cwd=REPO_DIR, timeout_s=self.timeout), on_output
        )
        if res2.exit_code != 0 or res2.image_id is None:
            raise SandboxError("dependency installation failed", res2)
        return res2.image_id

    async def provision_prebuilt(self, image_ref: str) -> str:
        """SWE-bench style images already contain the repo and its environment."""
        return await self.backend.base_image(image_ref)

    async def _detect_install(self, image_id: str) -> str:
        for path, cmd in (
            (f"{REPO_DIR}/pyproject.toml", "python -m pip install -q -e . pytest"),
            (f"{REPO_DIR}/setup.py", "python -m pip install -q -e . pytest"),
            (f"{REPO_DIR}/requirements.txt", "python -m pip install -q -r requirements.txt pytest"),
        ):
            try:
                await self.backend.read_file(image_id, path)
                return cmd
            except FileNotFoundError:
                continue
        return "python -m pip install -q pytest"

    # ---- tests --------------------------------------------------------------------------------

    async def run_tests(
        self, image_id: str, test_command: str, on_output: OutputHook | None
    ) -> tuple[RunResult, TestReport]:
        """Run the suite on a throwaway fork. Per-test results come from a JUnit report when available."""
        cmd = ensure_pytest_flags(test_command)
        res = await self.backend.run(
            image_id, RunSpec(shell=cmd, cwd=REPO_DIR, timeout_s=self.timeout, keep=True), on_output
        )
        report: TestReport | None = None
        if res.image_id is not None and "--junitxml" in cmd:
            try:
                report = parse_junit(await self.backend.read_file(res.image_id, JUNIT_ABSOLUTE), res.exit_code)
            except FileNotFoundError:
                report = None
        if report is None or not report.parsed:
            report = parse_pytest(res.combined, res.exit_code)
        return res, report

    @traced("sandbox.baseline", run_type="tool")
    async def baseline(self, image_id: str, test_command: str, on_output: OutputHook | None) -> Baseline:
        res, report = await self.run_tests(image_id, test_command, on_output)
        return Baseline(image_id=image_id, report=report, output=res.combined)

    @traced("sandbox.try_patch", run_type="tool")
    async def try_patch(
        self, base_image: str, patch: str, test_command: str, on_output: OutputHook | None
    ) -> AttemptRun:
        """Fork the baseline image, apply the patch, run tests. The baseline is never mutated."""
        apply_cmd = (
            "git apply --check ../archon.patch && git apply --whitespace=nowarn ../archon.patch && git status --short"
        )
        applied = await self.backend.run(
            base_image,
            RunSpec(shell=apply_cmd, cwd=REPO_DIR, timeout_s=120, files={PATCH_PATH: patch.encode("utf-8")}),
            on_output,
        )
        if applied.exit_code != 0 or applied.image_id is None:
            return AttemptRun(
                image_id=None,
                applied=False,
                report=None,
                output=applied.combined,
                exit_code=applied.exit_code,
            )
        res, report = await self.run_tests(applied.image_id, test_command, on_output)
        return AttemptRun(
            image_id=applied.image_id,
            applied=True,
            report=report,
            output=res.combined,
            exit_code=res.exit_code,
        )

    # ---- code reading -------------------------------------------------------------------------

    async def read_repo_file(self, image_id: str, rel_path: str) -> str | None:
        rel_path = rel_path.lstrip("/")
        if ".." in rel_path.split("/"):
            return None
        try:
            data = await self.backend.read_file(image_id, f"{REPO_DIR}/{rel_path}")
        except FileNotFoundError:
            return None
        text = data.decode("utf-8", errors="replace")
        if len(text) > MAX_EXCERPT_BYTES:
            text = text[:MAX_EXCERPT_BYTES] + f"\n... [truncated {len(text) - MAX_EXCERPT_BYTES} chars]"
        return text

    async def read_many(self, image_id: str, rel_paths: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for p in rel_paths[:8]:
            text = await self.read_repo_file(image_id, p)
            if text is not None:
                out[p] = text
        return out

    async def search(self, image_id: str, patterns: list[str], max_lines: int = 200) -> str:
        """Locate call sites with ripgrep, falling back to grep. Output is line-numbered."""
        if not patterns:
            return ""
        rg_args = " ".join(f"-e {shlex.quote(p)}" for p in patterns)
        grep_args = " ".join(f"-e {shlex.quote(p)}" for p in patterns)
        cmd = (
            f"(command -v rg >/dev/null && rg -n --no-heading --glob '!*.lock' --glob '!node_modules' "
            f"--glob '!.git' {rg_args} . || grep -rn --exclude-dir=.git --exclude-dir=node_modules {grep_args} .) "
            f"| head -n {max_lines}"
        )
        res = await self.backend.run(image_id, RunSpec(shell=cmd, cwd=REPO_DIR, timeout_s=120, keep=False), None)
        return res.stdout

    async def list_files(self, image_id: str, limit: int = 400) -> list[str]:
        res = await self.backend.run(
            image_id,
            RunSpec(shell=f"git ls-files | head -n {limit}", cwd=REPO_DIR, timeout_s=60, keep=False),
            None,
        )
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
