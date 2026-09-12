"""High-level sandbox operations used by the mission runner. Backend-agnostic."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.core.models import Candidate, TestReport
from app.core.patches import EditError, apply_edits
from app.observability.tracing import traced
from app.sandbox.base import REPO_DIR, OutputHook, RunResult, RunSpec, SandboxBackend, SandboxError
from app.sandbox.pytest_parser import ensure_pytest_flags, parse_junit, parse_pytest

# Slim base images ship without git. Install it once; the result is checkpointed so later steps inherit it.
ENSURE_GIT = (
    "(command -v git >/dev/null 2>&1 || (apt-get update -qq >/dev/null 2>&1 && "
    "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git ca-certificates >/dev/null 2>&1))"
)
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
    patch_text: str = ""


@dataclass
class Applied:
    """Result of writing a candidate into a fork, before tests run."""

    image_id: str | None
    patch_text: str
    error: str | None
    output: str = ""


class SandboxService:
    def __init__(
        self, backend: SandboxBackend, *, base_image_ref: str, command_timeout_s: int, repo_dir: str = REPO_DIR
    ) -> None:
        self.backend = backend
        self.base_image_ref = base_image_ref
        self.timeout = command_timeout_s
        self.repo_dir = repo_dir.rstrip("/") or "/"

    def with_repo_dir(self, repo_dir: str) -> SandboxService:
        """Same backend, different repository location (SWE-bench images keep the repo at /testbed)."""
        return SandboxService(
            self.backend, base_image_ref=self.base_image_ref, command_timeout_s=self.timeout, repo_dir=repo_dir
        )

    @property
    def scratch_dir(self) -> str:
        parent = str(PurePosixPath(self.repo_dir).parent)
        return parent if parent != "/" else ""

    @property
    def patch_path(self) -> str:
        return f"{self.scratch_dir}/archon.patch"

    @property
    def junit_path(self) -> str:
        return f"{self.scratch_dir}/archon-junit.xml"

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
        # Command paths stay relative to the working directory: the development local backend maps only the
        # working directory into its copy-on-fork tree, while real sandboxes accept either form.
        target = shlex.quote(PurePosixPath(self.repo_dir).name)
        clone = (
            f"{ENSURE_GIT} && git clone --quiet --depth 200 {shlex.quote(repo_url)} {target} "
            f"&& cd {target} && git checkout --quiet {shlex.quote(git_ref)} && git log --oneline -1"
        )
        res = await self.backend.run(
            base,
            RunSpec(
                shell=clone,
                cwd=self.scratch_dir or "/",
                timeout_s=min(self.timeout, 600),
                env={"GIT_TERMINAL_PROMPT": "0"},
            ),
            on_output,
        )
        if res.exit_code != 0 or res.image_id is None:
            hint = ""
            if "could not read Username" in res.stderr or "Authentication failed" in res.stderr:
                hint = " (the repository is private or does not exist; ARCHON clones public repositories only)"
            raise SandboxError(f"git clone or checkout failed{hint}", res)
        install = install_command or await self._detect_install(res.image_id)
        res2 = await self.backend.run(
            res.image_id, RunSpec(shell=install, cwd=self.repo_dir, timeout_s=self.timeout), on_output
        )
        if res2.exit_code != 0 or res2.image_id is None:
            raise SandboxError("dependency installation failed", res2)
        return res2.image_id

    async def provision_prebuilt(
        self, image_ref: str, test_patch: str = "", on_output: OutputHook | None = None
    ) -> str:
        """SWE-bench style images already contain the repo and its environment. The instance's test patch adds
        the tests that must go from failing to passing; applying it first is what the SWE-bench harness does."""
        image = await self.backend.base_image(image_ref)
        if not test_patch.strip():
            return image
        res = await self.backend.run(
            image,
            RunSpec(
                shell="git apply --whitespace=nowarn ../archon.patch && git status --short | head -20",
                cwd=self.repo_dir,
                timeout_s=120,
                files={self.patch_path: test_patch.encode("utf-8")},
            ),
            on_output,
        )
        if res.exit_code != 0 or res.image_id is None:
            raise SandboxError("could not apply the instance test patch", res)
        return res.image_id

    async def _detect_install(self, image_id: str) -> str:
        for path, cmd in (
            (f"{self.repo_dir}/pyproject.toml", "python -m pip install -q -e . pytest"),
            (f"{self.repo_dir}/setup.py", "python -m pip install -q -e . pytest"),
            (f"{self.repo_dir}/requirements.txt", "python -m pip install -q -r requirements.txt pytest"),
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
            image_id, RunSpec(shell=cmd, cwd=self.repo_dir, timeout_s=self.timeout, keep=True), on_output
        )
        report: TestReport | None = None
        if res.image_id is not None and "--junitxml" in cmd:
            try:
                report = parse_junit(await self.backend.read_file(res.image_id, self.junit_path), res.exit_code)
            except FileNotFoundError:
                report = None
        if report is None or not report.parsed:
            report = parse_pytest(res.combined, res.exit_code)
        return res, report

    @traced("sandbox.baseline", run_type="tool")
    async def baseline(self, image_id: str, test_command: str, on_output: OutputHook | None) -> Baseline:
        res, report = await self.run_tests(image_id, test_command, on_output)
        return Baseline(image_id=image_id, report=report, output=res.combined)

    @traced("sandbox.apply_candidate", run_type="tool")
    async def apply_candidate(
        self,
        base_image: str,
        candidate: Candidate,
        originals: dict[str, str],
        on_output: OutputHook | None,
    ) -> Applied:
        """Fork the baseline and write the candidate into it. Edits are applied here and the diff is produced
        by git inside the fork, so the model never has to get hunk headers right."""
        if candidate.uses_edits:
            return await self._apply_edits(base_image, candidate, originals, on_output)
        return await self._apply_patch(base_image, candidate.patch, on_output)

    async def _apply_edits(
        self, base_image: str, candidate: Candidate, originals: dict[str, str], on_output: OutputHook | None
    ) -> Applied:
        new_contents: dict[str, str] = {}
        by_path: dict[str, list[tuple[str, str]]] = {}
        for e in candidate.edits:
            by_path.setdefault(e.path.lstrip("/"), []).append((e.search, e.replace))
        for path, pairs in by_path.items():
            original = originals.get(path)
            if original is None:
                original = await self.read_repo_file(base_image, path)
            if original is None:
                return Applied(None, "", f"{path}: file not found in repository; use files[] to create new files")
            try:
                new_contents[path] = apply_edits(original, pairs, path)
            except EditError as exc:
                return Applied(None, "", str(exc))
        for f in candidate.files:
            new_contents[f.path.lstrip("/")] = f.content
        if not new_contents:
            return Applied(None, "", "candidate contained no changes")
        for path in new_contents:
            if ".." in path.split("/") or path.startswith(".git/"):
                return Applied(None, "", f"refusing to write outside the repository: {path}")
        uploads = {f"{self.repo_dir}/{path}": content.encode("utf-8") for path, content in new_contents.items()}
        quoted = " ".join(shlex.quote(p) for p in new_contents)
        cmd = f"git add -- {quoted} && git diff --cached --no-color -- {quoted}"
        res = await self.backend.run(
            base_image, RunSpec(shell=cmd, cwd=self.repo_dir, timeout_s=120, files=uploads), on_output
        )
        if res.exit_code != 0 or res.image_id is None:
            return Applied(None, "", f"git could not stage the edited files: {res.stderr[-800:]}", res.combined)
        patch_text = res.stdout if res.stdout.strip() else ""
        if not patch_text:
            return Applied(None, "", "the edits produced no change to the repository", res.combined)
        return Applied(res.image_id, patch_text, None, res.combined)

    async def _apply_patch(self, base_image: str, patch: str, on_output: OutputHook | None) -> Applied:
        pp = "../archon.patch"  # relative to the repo dir; the file is uploaded at self.patch_path
        apply_cmd = (
            f"(git apply --whitespace=nowarn {pp} || git apply --3way --whitespace=nowarn {pp}) "
            "&& git add -A -- . ':!.venv' && git diff --cached --no-color"
        )
        res = await self.backend.run(
            base_image,
            RunSpec(shell=apply_cmd, cwd=self.repo_dir, timeout_s=120, files={self.patch_path: patch.encode("utf-8")}),
            on_output,
        )
        if res.exit_code != 0 or res.image_id is None:
            return Applied(None, "", f"git apply failed: {res.stderr[-1200:] or res.stdout[-800:]}", res.combined)
        return Applied(res.image_id, res.stdout if res.stdout.strip() else patch, None, res.combined)

    @traced("sandbox.try_patch", run_type="tool")
    async def try_patch(
        self, base_image: str, patch: str, test_command: str, on_output: OutputHook | None
    ) -> AttemptRun:
        """Apply a unified diff on a fork and run the tests. Kept for callers that already hold a diff."""
        applied = await self._apply_patch(base_image, patch, on_output)
        if applied.error or applied.image_id is None:
            return AttemptRun(None, False, None, applied.output or (applied.error or ""), 128)
        res, report = await self.run_tests(applied.image_id, test_command, on_output)
        return AttemptRun(applied.image_id, True, report, res.combined, res.exit_code, applied.patch_text)

    # ---- code reading -------------------------------------------------------------------------

    def normalize_path(self, path: str) -> str:
        """Accept absolute sandbox paths, ./ prefixes, and repo-relative paths; return repo-relative."""
        p = path.strip()
        prefix = self.repo_dir.rstrip("/") + "/"
        if p.startswith(prefix):
            p = p[len(prefix) :]
        while p.startswith("./"):
            p = p[2:]
        return p.lstrip("/")

    async def read_repo_file(self, image_id: str, rel_path: str) -> str | None:
        rel_path = self.normalize_path(rel_path)
        if not rel_path or ".." in rel_path.split("/"):
            return None
        try:
            data = await self.backend.read_file(image_id, f"{self.repo_dir}/{rel_path}")
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
        res = await self.backend.run(image_id, RunSpec(shell=cmd, cwd=self.repo_dir, timeout_s=120, keep=False), None)
        return res.stdout

    async def list_files(self, image_id: str, limit: int = 600) -> list[str]:
        """Tracked source files, code first, docs and data last, so the engineer can name real paths."""
        cmd = (
            "git ls-files | grep -vE '\\.(png|jpg|jpeg|gif|ico|svg|woff2?|ttf|pdf|lock|min\\.js|map)$' "
            f"| grep -vE '^(docs?|doc|examples?|benchmarks?)/' | head -n {limit}"
        )
        res = await self.backend.run(image_id, RunSpec(shell=cmd, cwd=self.repo_dir, timeout_s=60, keep=False), None)
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
