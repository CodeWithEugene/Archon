"""Scripted sandbox for unit tests. Matches commands by regex and returns canned results."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.models import new_id
from app.sandbox.base import OutputHook, RunResult, RunSpec, emit_lines

Predicate = Callable[[str, dict[str, bytes]], bool]


@dataclass
class Rule:
    pattern: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    once: bool = False
    when: Predicate | None = None
    used: bool = field(default=False, repr=False)


class FakeBackend:
    """Rules are evaluated in order; the first whose regex matches the shell (and whose predicate,
    given the shell and the image's files, returns True) wins. Files written via RunSpec.files
    persist into the produced image so later runs can be conditioned on the patch content."""

    name = "fake"

    def __init__(self, default_files: dict[str, bytes] | None = None) -> None:
        self.rules: list[Rule] = []
        self.calls: list[RunSpec] = []
        self.files: dict[str, dict[str, bytes]] = {}
        self.default_files = dict(default_files or {})

    def on(
        self,
        pattern: str,
        *,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
        once: bool = False,
        when: Predicate | None = None,
    ) -> None:
        self.rules.append(
            Rule(pattern=pattern, exit_code=exit_code, stdout=stdout, stderr=stderr, once=once, when=when)
        )

    def seed_file(self, image_id: str, path: str, data: bytes) -> None:
        self.files.setdefault(image_id, {})[path] = data

    async def base_image(self, ref: str) -> str:
        image_id = new_id("img")
        self.files[image_id] = dict(self.default_files)
        return image_id

    async def run(self, image_id: str, spec: RunSpec, on_output: OutputHook | None = None) -> RunResult:
        self.calls.append(spec)
        if on_output is not None:
            await on_output("cmd", f"$ {spec.shell}")
        image_files = {**self.files.get(image_id, {}), **spec.files}
        matched: Rule | None = None
        for rule in self.rules:
            if rule.once and rule.used:
                continue
            if not re.search(rule.pattern, spec.shell):
                continue
            if rule.when is not None and not rule.when(spec.shell, image_files):
                continue
            matched = rule
            break
        if matched is None:
            matched = Rule(pattern="", exit_code=0)
        matched.used = True
        produced = new_id("img") if spec.keep else None
        if produced:
            self.files[produced] = image_files
        await emit_lines(on_output, "stdout", matched.stdout)
        await emit_lines(on_output, "stderr", matched.stderr)
        return RunResult(exit_code=matched.exit_code, stdout=matched.stdout, stderr=matched.stderr, image_id=produced)

    async def read_file(self, image_id: str, path: str) -> bytes:
        try:
            return self.files[image_id][path]
        except KeyError as exc:
            raise FileNotFoundError(path) from exc

    async def close(self) -> None:
        return None
