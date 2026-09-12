"""Token Factory Sandboxes backend using contree-sdk 0.3.x."""

from __future__ import annotations

import logging
import shlex
import time
from typing import Any

from app.sandbox.base import OutputHook, RunResult, RunSpec, SandboxError, emit_lines

logger = logging.getLogger(__name__)


class ContreeBackend:
    """Thin wrapper. Every run() with keep=True produces a new immutable image we can fork from."""

    name = "contree"

    def __init__(self, *, token: str, base_url: str, project_id: str, operation_timeout_s: int = 1800) -> None:
        from contree_sdk import Contree
        from contree_sdk.auth import IAMAuth
        from contree_sdk.config import ContreeConfig

        if not token or not project_id:
            raise SandboxError("contree backend needs NEBIUS_API_KEY and NEBIUS_PROJECT_ID")
        auth = IAMAuth(token=token, project_id=project_id, base_url=base_url)
        config = ContreeConfig(auth=auth, operation_timeout=float(operation_timeout_s), transport_timeout=30.0)
        self._sdk: Any = Contree(config)

    async def whoami(self) -> dict[str, Any]:
        info = await self._sdk.get_token_info()
        return {"limits": getattr(info, "limits", {}), "expires": getattr(info, "token_expiration", None)}

    async def base_image(self, ref: str) -> str:
        # Public catalog images (python:3.12-slim, swebench/...) and our own images resolve by tag.
        # Anything else is imported from a registry.
        try:
            image = await self._sdk.images.use(ref, strict=True)
        except Exception:
            image = await self._sdk.images.oci(ref if "://" in ref else f"docker://docker.io/library/{ref}")
        uuid = await image.image_uuid() if hasattr(image, "image_uuid") else image.uuid
        if uuid is None:
            raise SandboxError(f"could not resolve base image {ref}")
        return str(uuid)

    async def run(self, image_id: str, spec: RunSpec, on_output: OutputHook | None = None) -> RunResult:
        image = await self._sdk.images.use(image_id, strict=False)
        if on_output is not None:
            await on_output("cmd", f"$ {spec.shell}")
        # Files are uploaded into the new image before the command runs.
        files: dict[str, bytes] | None = dict(spec.files) if spec.files else None
        # Ensure the working directory exists without requiring an extra round trip, and run under bash when
        # the image has it: the Sandboxes default shell is /bin/sh, where conda activation and `source` do not work.
        inner = f"mkdir -p {shlex.quote(spec.cwd)} && cd {shlex.quote(spec.cwd)} && ({spec.shell})"
        shell = f"if command -v bash >/dev/null 2>&1; then exec bash -c {shlex.quote(inner)}; else {inner}; fi"
        started = time.monotonic()
        try:
            result_image = await image.run(
                shell=shell,
                env=spec.env or None,
                files=files,
                timeout=float(spec.timeout_s),
                disposable=not spec.keep,
                truncate_output_at=spec.truncate_at,
            )
        except Exception as exc:  # contree raises many specific exception types
            name = type(exc).__name__
            timed_out = "TimedOut" in name or "Timeout" in name
            await emit_lines(on_output, "stderr", f"[sandbox error] {name}: {exc}")
            return RunResult(
                exit_code=124 if timed_out else 125,
                stdout="",
                stderr=f"{name}: {exc}",
                image_id=None,
                elapsed_s=time.monotonic() - started,
                timed_out=timed_out,
            )
        res = result_image.result
        stdout = _as_text(res.stdout)
        stderr = _as_text(res.stderr)
        await emit_lines(on_output, "stdout", stdout)
        await emit_lines(on_output, "stderr", stderr)
        new_id = str(result_image.uuid) if spec.keep and result_image.uuid is not None else None
        return RunResult(
            exit_code=int(res.exit_code),
            stdout=stdout,
            stderr=stderr,
            image_id=new_id,
            elapsed_s=res.elapsed_time.total_seconds(),
            truncated=bool(res.truncated),
            cost=float(getattr(res, "cost", 0.0) or 0.0),
        )

    async def read_file(self, image_id: str, path: str) -> bytes:
        from contree_sdk.sdk.exceptions import NotFoundError

        image = await self._sdk.images.use(image_id, strict=False)
        try:
            data: bytes = await image.read(path)
        except NotFoundError as exc:
            raise FileNotFoundError(path) from exc
        return data

    async def close(self) -> None:
        close = getattr(self._sdk, "aclose", None) or getattr(self._sdk, "close", None)
        if close is not None:
            try:
                maybe = close()
                if hasattr(maybe, "__await__"):
                    await maybe
            except Exception as exc:  # pragma: no cover
                logger.debug("contree close failed: %s", exc)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    read = getattr(value, "getvalue", None)
    if callable(read):
        got = read()
        return got.decode("utf-8", errors="replace") if isinstance(got, bytes) else str(got)
    return str(value)
