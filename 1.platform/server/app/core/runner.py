"""The mission state machine. Deterministic control flow; models are called only inside roles."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.core.events import EventBus
from app.core.models import (
    Attempt,
    Candidate,
    DiffFile,
    EventKind,
    Mission,
    MissionStatus,
    MissionType,
    ModelUsage,
    TestReport,
    new_id,
    utcnow,
)
from app.core.patches import check_patch_safety, inspect_patch
from app.core.pricing import PriceTable
from app.core.scoring import best_attempt, is_resolved, score_attempt
from app.grounding.tavily import Grounder, SearchResult
from app.llm.client import LLM, LLMError, UsageHook
from app.missions.migration import run_parity_sample, scan_repository
from app.missions.swe import SweCatalog
from app.observability.tracing import annotate, current_trace_url, traced
from app.roles.compactor import Compactor, Narrator
from app.roles.engineer import Engineer, EngineerRequest
from app.roles.researcher import Researcher
from app.roles.reviewer import Reviewer
from app.sandbox.base import SandboxError
from app.sandbox.pytest_parser import detect_libraries
from app.sandbox.service import Baseline, SandboxService
from app.settings import Settings
from app.store.db import Store

logger = logging.getLogger(__name__)
LLMFactory = Callable[[UsageHook], LLM]
TRACEBACK_PATH = re.compile(r'File "([^"]+)", line \d+')
LANG_BY_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
}


class Aborted(Exception):
    pass


@dataclass
class RunnerDeps:
    store: Store
    bus: EventBus
    sandbox: SandboxService
    llm_factory: LLMFactory
    grounder: Grounder
    prices: PriceTable
    settings: Settings
    swe: SweCatalog
    on_finished: Callable[[Mission], Awaitable[None]] | None = None


class MissionRunner:
    def __init__(self, mission: Mission, deps: RunnerDeps) -> None:
        self.m = mission
        self.d = deps
        self._abort_reason: str | None = None
        self.spend = 0.0
        self.llm: LLM = deps.llm_factory(self._usage_hook)
        self.engineer = Engineer(self.llm, deps.sandbox)
        self.reviewer = Reviewer(self.llm, allow_test_edits=True)
        self.researcher = Researcher(self.llm, deps.grounder)
        self.compactor = Compactor(self.llm)
        self.narrator = Narrator(self.llm, use_model=deps.settings.narrate_with_super)

    # ---- plumbing -------------------------------------------------------------------------------

    def abort(self, reason: str = "aborted by user") -> None:
        self._abort_reason = reason

    def _check_abort(self) -> None:
        if self._abort_reason:
            raise Aborted(self._abort_reason)

    async def _usage_hook(self, model: str, task: str, pt: int, ct: int, cost: float) -> None:
        self.spend += cost
        self.m.spend_usd = round(self.spend, 6)
        await self.d.store.save_usage(
            ModelUsage(
                mission_id=self.m.id,
                model=model,
                task=task,
                prompt_tokens=pt,
                completion_tokens=ct,
                cost_usd=cost,
            )
        )
        await self._emit(
            EventKind.USAGE,
            {
                "model": model,
                "task": task,
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "cost_usd": round(cost, 6),
            },
        )
        if self.spend > self.d.settings.max_mission_usd and not self._abort_reason:
            self._abort_reason = f"spend cap reached: ${self.spend:.2f} > ${self.d.settings.max_mission_usd:.2f}"

    async def _emit(self, kind: EventKind, payload: dict[str, object]) -> None:
        await self.d.bus.publish(self.m.id, kind, payload)

    async def _status(self, status: MissionStatus) -> None:
        self.m.status = status
        await self.d.store.save_mission(self.m)
        await self._emit(EventKind.STATUS, {"status": status.value, "iteration": self.m.iteration})

    async def _thought(self, stage: str, text: str, model: str = "archon") -> None:
        await self._emit(EventKind.THOUGHT, {"stage": stage, "model": model, "text": text[:4000]})

    async def _narrate(self, state: str, detail: str = "") -> None:
        await self._thought(
            state,
            await self.narrator.narrate(state, detail),
            self.d.settings.super_model if self.narrator.use_model else "archon",
        )

    def _terminal(self, attempt_id: str) -> Callable[[str, str], Awaitable[None]]:
        async def hook(stream: str, line: str) -> None:
            await self._emit(EventKind.TERMINAL, {"attempt": attempt_id, "stream": stream, "line": line[:2000]})

        return hook

    async def _finish(self, status: MissionStatus, payload: dict[str, object]) -> None:
        self.m.status = status
        self.m.finished_at = utcnow()
        await self.d.store.save_mission(self.m)
        await self._emit(
            EventKind.DONE,
            {
                "status": status.value,
                "selected_attempt": self.m.selected_attempt,
                "iterations": self.m.iteration,
                "spend_usd": round(self.spend, 4),
                "trace_url": self.m.summary.get("trace_url"),
                **payload,
            },
        )
        if self.d.on_finished is not None:
            await self.d.on_finished(self.m)

    # ---- main -----------------------------------------------------------------------------------

    @traced("archon.mission", run_type="chain")
    async def run(self) -> Mission:
        annotate(
            metadata={
                "mission_id": self.m.id,
                "mission_type": self.m.type.value,
                "target": self.m.repo_url or self.m.swe_instance_id or "",
            },
            tags=[self.m.type.value.lower()],
        )
        self.m.summary["trace_url"] = current_trace_url()
        try:
            await self._run()
        except Aborted as exc:
            self.m.failure_report = str(exc)
            await self._emit(EventKind.ERROR, {"message": str(exc)})
            await self._finish(MissionStatus.ABORTED, {"reason": str(exc)})
        except SandboxError as exc:
            detail = exc.result.combined[-4000:] if exc.result else ""
            self.m.failure_report = f"{exc}\n{detail}"
            await self._emit(EventKind.ERROR, {"message": f"sandbox: {exc}", "detail": detail[-2000:]})
            await self._finish(MissionStatus.FAILED, {"reason": str(exc)})
        except LLMError as exc:
            self.m.failure_report = f"model error: {exc}"
            await self._emit(EventKind.ERROR, {"message": f"model: {exc}"})
            await self._finish(MissionStatus.FAILED, {"reason": str(exc)})
        except Exception as exc:  # noqa: BLE001
            logger.exception("mission %s crashed", self.m.id)
            self.m.failure_report = f"internal error: {type(exc).__name__}: {exc}"
            await self._emit(EventKind.ERROR, {"message": self.m.failure_report})
            await self._finish(MissionStatus.FAILED, {"reason": self.m.failure_report})
        return self.m

    async def _run(self) -> None:
        s = self.d.settings
        # 1. provision
        await self._status(MissionStatus.PROVISIONING)
        await self._narrate("PROVISIONING")
        image = await self._provision()
        self._check_abort()

        # 2. baseline
        await self._status(MissionStatus.REPRODUCING)
        await self._narrate("REPRODUCING")
        test_cmd = self._test_command()
        base = await self.d.sandbox.baseline(image, test_cmd, self._terminal("baseline"))
        self.m.baseline_image = base.image_id
        self.m.baseline_report = base.report
        await self._emit_tests("baseline", base.report)
        self._check_abort()

        if self.m.type == MissionType.BUG_HEALING and base.report.exit_code == 0:
            await self._thought(
                "REPRODUCING", "The test suite already passes on the untouched checkout. Nothing to fix."
            )
            await self._finish(MissionStatus.NOTHING_TO_FIX, {})
            return
        if self.m.type == MissionType.MIGRATION and base.report.exit_code != 0:
            self.m.failure_report = (
                "Migration requires a green baseline. The repository's tests fail before any change."
            )
            await self._emit(EventKind.ERROR, {"message": self.m.failure_report})
            await self._finish(MissionStatus.FAILED, {"reason": "baseline red"})
            return

        # 3. grounding (bug healing) or scan (migration)
        failing_output = await self.compactor.compact(base.output)
        brief: str | None = None
        migration: dict[str, object] | None = None
        if self.m.type == MissionType.BUG_HEALING:
            await self._status(MissionStatus.GROUNDING)
            await self._narrate("GROUNDING")
            rb = await self.researcher.research(failing_output, detect_libraries(base.output), self._on_search)
            if rb.brief:
                brief = rb.brief
                await self._thought("GROUNDING", f"Research brief: {rb.brief[:1500]}", s.super_model)
            else:
                await self._thought("GROUNDING", f"Continuing without web grounding: {rb.skipped_reason}")
        else:
            await self._status(MissionStatus.GROUNDING)
            await self._thought(
                "GROUNDING", "Scanning the repository for closed-provider client calls and model names."
            )
            scan = await scan_repository(self.d.sandbox, base.image_id, self.d.prices)
            self.m.summary["migration_scan"] = scan.summary()
            migration = {"base_url": s.nebius_base_url, "locations": scan.locations, "mapping": scan.mapping}
            await self._thought(
                "GROUNDING",
                f"Found {len(scan.files)} file(s) and {len(scan.source_models)} model literal(s): "
                f"{', '.join(scan.source_models) or 'none'}.",
            )
            if not scan.files:
                self.m.failure_report = "No OpenAI or Anthropic client calls were found. Nothing to migrate."
                await self._finish(MissionStatus.NOTHING_TO_FIX, {})
                return
        self._check_abort()

        # 4. iterate
        excerpts = await self._initial_excerpts(base.image_id, base.output, migration)
        previous: Attempt | None = None
        previous_output: str | None = None
        for iteration in range(1, s.max_iterations + 1):
            self.m.iteration = iteration
            await self._status(MissionStatus.REASONING)
            await self._narrate("REASONING", f"Iteration {iteration} of {s.max_iterations}.")
            req = EngineerRequest(
                image_id=base.image_id,
                failing_output=failing_output,
                excerpts=excerpts,
                brief=brief,
                previous=previous,
                previous_output=previous_output,
                hint=self.m.hint,
                n_candidates=s.candidates_per_iteration,
                migration=migration,
            )
            out = await self.engineer.propose(req)
            self._check_abort()
            await self._thought("REASONING", f"Root cause: {out.root_cause}", s.ultra_model)

            await self._status(MissionStatus.TESTING)
            await self._narrate("TESTING", f"{len(out.candidates)} candidate(s).")
            attempts = await self._test_candidates(base, iteration, out.candidates, test_cmd)
            self._check_abort()

            best = best_attempt(attempts)
            if best is not None and is_resolved(base.report, best):
                await self._status(MissionStatus.REVIEWING)
                await self._narrate("REVIEWING")
                review = await self.reviewer.review(
                    best.patch, out.root_cause, best.report.summary if best.report else ""
                )
                await self._emit(
                    EventKind.REVIEW,
                    {"attempt": best.id, "verdict": review.verdict, "reasons": review.reasons},
                )
                if review.verdict == "APPROVE":
                    best.selected = True
                    await self.d.store.save_attempt(best)
                    self.m.selected_attempt = best.id
                    self.m.diff = await self._build_diff(base.image_id, best)
                    if migration is not None:
                        await self._parity(base.image_id)
                    self.m.summary["root_cause"] = out.root_cause
                    await self._finish(
                        MissionStatus.VERIFIED, {"fail_to_pass": best.fail_to_pass, "pass_to_pass_broken": 0}
                    )
                    return
                previous, previous_output = best, "Reviewer rejected the patch: " + "; ".join(review.reasons)
                continue

            previous = best
            previous_output = (
                await self.compactor.compact(best.report_output)
                if best and best.report_output
                else (best.error if best else None)
            )

        self.m.failure_report = f"No candidate resolved the failure within {s.max_iterations} iterations."
        await self._emit(EventKind.ERROR, {"message": self.m.failure_report})
        await self._finish(MissionStatus.FAILED, {"reason": "iteration limit"})

    # ---- steps ----------------------------------------------------------------------------------

    async def _provision(self) -> str:
        if self.m.swe_instance_id:
            inst = self.d.swe.get(self.m.swe_instance_id)
            if inst is None:
                raise SandboxError(f"unknown SWE-bench instance {self.m.swe_instance_id}")
            self.m.test_command = inst.test_command
            self.m.repo_url = inst.repo
            return await self.d.sandbox.provision_prebuilt(inst.image)
        assert self.m.repo_url is not None
        return await self.d.sandbox.provision_repo(
            self.m.repo_url, self.m.git_ref, self.m.install_command, self._terminal("baseline")
        )

    def _test_command(self) -> str:
        if not self.m.test_command:
            raise SandboxError("mission has no test command")
        return self.m.test_command

    async def _on_search(self, r: SearchResult) -> None:
        await self._emit(
            EventKind.TAVILY,
            {"query": r.query, "results": len(r.hits), "ms": r.ms, "error": r.error, "cached": r.cached},
        )

    async def _emit_tests(self, attempt_id: str, report: TestReport, fail_to_pass: int = 0, broken: int = 0) -> None:
        await self._emit(
            EventKind.TESTS,
            {
                "attempt": attempt_id,
                "exit_code": report.exit_code,
                "passed": len(report.passed),
                "failed": len(report.failed) + len(report.errors),
                "total": report.total,
                "fail_to_pass": fail_to_pass,
                "pass_to_pass_broken": broken,
                "summary": report.summary[:300],
            },
        )

    async def _initial_excerpts(
        self, image_id: str, output: str, migration: dict[str, object] | None
    ) -> dict[str, str]:
        paths: dict[str, None] = {}
        if migration is not None:
            scan_files = (
                self.m.summary.get("migration_scan", {}).get("files", [])
                if isinstance(self.m.summary.get("migration_scan"), dict)
                else []
            )
            for p in scan_files:
                paths.setdefault(str(p), None)
        for m in TRACEBACK_PATH.finditer(output):
            p = m.group(1)
            if "site-packages" in p or p.startswith("<"):
                continue
            rel = p.split("/repo/", 1)[1] if "/repo/" in p else p.lstrip("./")
            paths.setdefault(rel, None)
        return await self.d.sandbox.read_many(image_id, list(paths)[:8])

    async def _test_candidates(
        self, base: Baseline, iteration: int, candidates: list[Candidate], test_cmd: str
    ) -> list[Attempt]:
        attempts: list[Attempt] = []
        for c in candidates:
            patch = c.patch
            info = inspect_patch(patch)
            a = Attempt(
                id=new_id("a"),
                mission_id=self.m.id,
                iteration=iteration,
                parent_image=base.image_id,
                patch=patch,
                rationale=c.rationale,
                patch_lines=info.lines,
            )
            attempts.append(a)
            await self._emit(
                EventKind.PATCH,
                {
                    "attempt": a.id,
                    "iteration": iteration,
                    "rationale": a.rationale[:500],
                    "files": [
                        {
                            "path": f,
                            "added": info.per_file.get(f, (0, 0))[0],
                            "removed": info.per_file.get(f, (0, 0))[1],
                        }
                        for f in info.files
                    ],
                },
            )

        async def run_one(a: Attempt) -> None:
            safety = check_patch_safety(a.patch)
            if not safety.ok:
                a.error = "rejected before execution: " + "; ".join(safety.problems)
                await self._emit(EventKind.TERMINAL, {"attempt": a.id, "stream": "stderr", "line": a.error})
                return
            try:
                res = await self.d.sandbox.try_patch(base.image_id, a.patch, test_cmd, self._terminal(a.id))
            except SandboxError as exc:
                a.error = str(exc)
                return
            a.applied, a.result_image, a.exit_code, a.report = (
                res.applied,
                res.image_id,
                res.exit_code,
                res.report,
            )
            a.report_output = res.output
            if not res.applied:
                a.error = "git apply failed"

        await asyncio.gather(*(run_one(a) for a in attempts))
        for a in attempts:
            score_attempt(base.report, a)
            await self.d.store.save_attempt(a)
            if a.report is not None:
                await self._emit_tests(a.id, a.report, a.fail_to_pass, a.pass_to_pass_broken)
            else:
                await self._emit(
                    EventKind.TESTS,
                    {
                        "attempt": a.id,
                        "exit_code": a.exit_code if a.exit_code is not None else 1,
                        "passed": 0,
                        "failed": 0,
                        "total": 0,
                        "fail_to_pass": 0,
                        "pass_to_pass_broken": a.pass_to_pass_broken,
                        "summary": a.error or "not applied",
                    },
                )
        return attempts

    async def _build_diff(self, base_image: str, best: Attempt) -> list[DiffFile]:
        if best.result_image is None:
            return []
        files: list[DiffFile] = []
        for path in inspect_patch(best.patch).files[:20]:
            original = await self.d.sandbox.read_repo_file(base_image, path) or ""
            modified = await self.d.sandbox.read_repo_file(best.result_image, path) or ""
            ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
            files.append(
                DiffFile(
                    path=path,
                    original=original,
                    modified=modified,
                    language=LANG_BY_EXT.get(ext, "plaintext"),
                )
            )
        return files

    async def _parity(self, image_id: str) -> None:
        try:
            result = await run_parity_sample(self.d.sandbox, image_id, self.llm)
        except Exception as exc:  # noqa: BLE001
            await self._thought("REVIEWING", f"Parity sample skipped: {type(exc).__name__}")
            return
        if result is None:
            await self._thought(
                "REVIEWING",
                "No parity_prompts.json in the repository; parity sample skipped. "
                "Mocked tests passing does not prove behavioral parity.",
            )
            return
        self.m.summary["parity"] = {
            "sampled": result.sampled,
            "mean_similarity": result.mean_similarity,
            "note": result.note,
            "per_prompt": result.per_prompt,
        }
        await self._thought(
            "REVIEWING",
            f"Parity sample: {result.sampled} prompts, mean similarity {result.mean_similarity:.2f}. {result.note}",
            self.d.settings.super_model,
        )
