"""Sandbox backend protocol. Images are immutable; every run yields a new image id."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

OutputHook = Callable[[str, str], Awaitable[None]]  # (stream, line)

WORKDIR = "/work"
REPO_DIR = f"{WORKDIR}/repo"


class SandboxError(RuntimeError):
    def __init__(self, message: str, result: RunResult | None = None) -> None:
        super().__init__(message)
        self.result = result


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    image_id: str | None
    elapsed_s: float = 0.0
    truncated: bool = False
    timed_out: bool = False
    cost: float = 0.0

    @property
    def combined(self) -> str:
        if self.stderr and self.stdout:
            return f"{self.stdout}\n{self.stderr}"
        return self.stdout or self.stderr


@dataclass
class RunSpec:
    shell: str
    cwd: str = WORKDIR
    timeout_s: int = 900
    env: dict[str, str] = field(default_factory=dict)
    files: dict[str, bytes] = field(default_factory=dict)
    keep: bool = True
    truncate_at: int = 2_000_000


class SandboxBackend(Protocol):
    name: str

    async def base_image(self, ref: str) -> str:
        """Resolve a base image reference (OCI tag or provider-specific id) to an image id."""
        ...

    async def run(self, image_id: str, spec: RunSpec, on_output: OutputHook | None = None) -> RunResult:
        """Execute a shell command against an image. Returns the new image id when spec.keep is True."""
        ...

    async def read_file(self, image_id: str, path: str) -> bytes:
        """Read a file from an image. Raises FileNotFoundError."""
        ...

    async def close(self) -> None: ...


async def emit_lines(on_output: OutputHook | None, stream: str, text: str, limit: int = 400) -> None:
    if on_output is None or not text:
        return
    lines = text.splitlines()
    if len(lines) > limit:
        head, tail = lines[: limit // 2], lines[-limit // 2 :]
        lines = [*head, f"... [{len(lines) - limit} lines omitted] ...", *tail]
    for line in lines:
        await on_output(stream, line)
