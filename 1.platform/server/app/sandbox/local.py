"""Development-only backend. Runs commands on this machine in copy-on-fork directories.

This executes target repository code on the host. It exists so the loop can be developed before
Sandboxes beta access is granted. It refuses to start in production.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path

from app.core.models import new_id
from app.sandbox.base import OutputHook, RunResult, RunSpec, SandboxError, emit_lines

logger = logging.getLogger(__name__)


class LocalBackend:
    name = "local"

    def __init__(self, root: Path | None = None, *, production: bool = False) -> None:
        if production:
            raise SandboxError("LocalBackend is not allowed in production")
        self.root = root or Path(tempfile.mkdtemp(prefix="archon-local-"))
        self.root.mkdir(parents=True, exist_ok=True)
        logger.warning("LocalBackend active: repository code will run on this machine under %s", self.root)

    def _dir(self, image_id: str) -> Path:
        p = self.root / image_id
        if not p.is_dir():
            raise SandboxError(f"unknown image {image_id}")
        return p

    def _map(self, image_dir: Path, path: str) -> Path:
        rel = path.lstrip("/")
        target = (image_dir / rel).resolve()
        if image_dir.resolve() not in target.parents and target != image_dir.resolve():
            raise SandboxError(f"path escapes image: {path}")
        return target

    async def base_image(self, ref: str) -> str:
        image_id = new_id("img")
        (self.root / image_id).mkdir()
        return image_id

    async def run(self, image_id: str, spec: RunSpec, on_output: OutputHook | None = None) -> RunResult:
        parent = self._dir(image_id)
        # Fork: copy the parent tree so siblings never see each other's writes.
        child_id = new_id("img")
        child = self.root / child_id
        await asyncio.to_thread(shutil.copytree, parent, child, symlinks=True)
        await asyncio.to_thread(_relocate, parent, child)
        for path, data in spec.files.items():
            target = self._map(child, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        cwd = self._map(child, spec.cwd)
        cwd.mkdir(parents=True, exist_ok=True)
        if on_output is not None:
            await on_output("cmd", f"$ {spec.shell}")
        env = {**os.environ, **spec.env, "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        started = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            "bash",
            "-lc",
            spec.shell,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timed_out = False
        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=spec.timeout_s)
        except TimeoutError:
            timed_out = True
            proc.kill()
            out_b, err_b = await proc.communicate()
        stdout = out_b.decode("utf-8", errors="replace")[-spec.truncate_at :]
        stderr = err_b.decode("utf-8", errors="replace")[-spec.truncate_at :]
        await emit_lines(on_output, "stdout", stdout)
        await emit_lines(on_output, "stderr", stderr)
        if timed_out:
            await emit_lines(on_output, "stderr", f"[timeout after {spec.timeout_s}s]")
        code = 124 if timed_out else (proc.returncode if proc.returncode is not None else 1)
        if not spec.keep:
            await asyncio.to_thread(shutil.rmtree, child, ignore_errors=True)
        return RunResult(
            exit_code=code,
            stdout=stdout,
            stderr=stderr,
            image_id=child_id if spec.keep else None,
            elapsed_s=time.monotonic() - started,
            timed_out=timed_out,
        )

    async def read_file(self, image_id: str, path: str) -> bytes:
        target = self._map(self._dir(image_id), path)
        if not target.is_file():
            raise FileNotFoundError(path)
        return await asyncio.to_thread(target.read_bytes)

    async def close(self) -> None:
        await asyncio.to_thread(shutil.rmtree, self.root, ignore_errors=True)


RELOCATE_GLOBS = (
    "**/pyvenv.cfg",
    "**/bin/activate*",
    "**/bin/*",
    "**/site-packages/*.pth",
    "**/site-packages/__editable__*",
    "**/site-packages/*.dist-info/direct_url.json",
    "**/site-packages/*.dist-info/RECORD",
    "**/*.egg-link",
)
MAX_RELOCATE_BYTES = 2_000_000


def _relocate(parent: Path, child: Path) -> None:
    """Rewrite absolute references to the parent image path inside copied virtualenvs.

    Editable installs (`pip install -e .`) and `bin/activate` embed the install-time absolute path. Without
    this, a fork would keep importing the parent's unpatched source. Real sandboxes do not need this because
    every fork mounts the repository at the same path.
    """
    old = str(parent.resolve()).encode()
    new = str(child.resolve()).encode()
    if old == new:
        return
    seen: set[Path] = set()
    for pattern in RELOCATE_GLOBS:
        for f in child.glob(pattern):
            if f in seen or not f.is_file() or f.is_symlink():
                continue
            seen.add(f)
            try:
                if f.stat().st_size > MAX_RELOCATE_BYTES:
                    continue
                data = f.read_bytes()
            except OSError:
                continue
            if old in data:
                try:
                    f.write_bytes(data.replace(old, new))
                except OSError:
                    continue
