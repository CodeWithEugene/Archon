"""Engineer: Nemotron 3 Ultra produces a root-cause note and candidate patches."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Any, cast

from pydantic import ValidationError

from app.core.models import Attempt, EngineerOutput
from app.core.patches import normalize_patch
from app.core.router import Task
from app.llm.client import LLM, LLMError
from app.llm.prompts import engineer_messages, migration_messages
from app.observability.tracing import traced
from app.sandbox.service import SandboxService

MAX_READ_ROUNDS = 4


@dataclass
class EngineerRequest:
    image_id: str
    failing_output: str
    excerpts: dict[str, str]
    brief: str | None
    previous: Attempt | None
    previous_output: str | None
    hint: str | None
    n_candidates: int
    migration: dict[str, object] | None = None  # {"base_url", "locations", "mapping"}
    file_listing: list[str] = field(default_factory=list)


class Engineer:
    def __init__(self, llm: LLM, sandbox: SandboxService) -> None:
        self.llm = llm
        self.sandbox = sandbox

    @traced("engineer.propose")
    async def propose(self, req: EngineerRequest) -> EngineerOutput:
        excerpts = dict(req.excerpts)
        last_error: str | None = None
        for _round in range(MAX_READ_ROUNDS + 1):
            messages = self._messages(req, excerpts)
            if last_error:
                messages.append(
                    {"role": "user", "content": f"Your previous output was rejected: {last_error}. Fix it."}
                )
            obj, _ = await self.llm.complete_json(self._task(req), messages, max_tokens=12_000)
            obj = coerce_engineer_output(obj, set(req.file_listing) | set(excerpts))
            try:
                out = EngineerOutput.model_validate(obj)
            except ValidationError as exc:
                last_error = _short(exc) + ". " + SCHEMA_REMINDER
                continue
            if out.candidates:
                for c in out.candidates:
                    if c.patch and not c.uses_edits:
                        c.patch = normalize_patch(c.patch)
                return out
            wanted = [p for p in out.files_to_read if self.sandbox.normalize_key(p) not in excerpts]
            if not wanted or _round >= MAX_READ_ROUNDS - 1:
                have = ", ".join(sorted(k for k in excerpts if not k.startswith("(")))
                last_error = (
                    "no more reading. You already have these files in full: "
                    f"{have}. Return candidates now with files_to_read empty."
                )
                continue
            more = await self.sandbox.read_many(req.image_id, wanted)
            found = {self.sandbox.normalize_path(p) for p in more}
            missing = [p for p in wanted if self.sandbox.normalize_path(p) not in found and p not in more]
            excerpts.update(more)
            if missing:
                notes = []
                for m in missing:
                    close = get_close_matches(self.sandbox.normalize_path(m), req.file_listing, n=3, cutoff=0.5)
                    notes.append(f"{m}: not found" + (f"; did you mean {', '.join(close)}?" if close else ""))
                excerpts["(missing files)"] = "\n".join(notes) + "\nUse exact paths from the repository file list."
        raise LLMError(f"engineer did not produce candidates after {MAX_READ_ROUNDS + 1} rounds: {last_error}")

    def _task(self, req: EngineerRequest) -> Task:
        return Task.MIGRATE if req.migration else Task.DIAGNOSE_AND_PATCH

    def _messages(self, req: EngineerRequest, excerpts: dict[str, str]) -> list[dict[str, str]]:
        if req.migration:
            return migration_messages(
                base_url=str(req.migration["base_url"]),
                locations=str(req.migration["locations"]),
                mapping=cast(dict[str, str], req.migration["mapping"]),
                excerpts=excerpts,
                file_listing=req.file_listing,
                previous=req.previous,
                previous_output=req.previous_output,
                hint=req.hint,
            )
        return engineer_messages(
            n_candidates=req.n_candidates,
            failing_output=req.failing_output,
            excerpts=excerpts,
            file_listing=req.file_listing,
            brief=req.brief,
            previous=req.previous,
            previous_output=req.previous_output,
            hint=req.hint,
        )


def _short(exc: ValidationError) -> str:
    errs = exc.errors()
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errs[:3])


SCHEMA_REMINDER = (
    'Required shape: {"root_cause": str, "files_to_read": [str], '
    '"candidates": [{"rationale": str, "edits": [{"path": str, "search": str, "replace": str}]}]}'
)


def coerce_engineer_output(obj: dict[str, Any], known_paths: set[str]) -> dict[str, Any]:
    """Accept the shapes Nemotron 3 Ultra sometimes produces instead of the schema.

    - top-level "edits" / "files" / "patch"       -> one candidate
    - {"path/to/file.py": "full content", ...}    -> one candidate with full-file replacements
    - "candidates" as a single object              -> list of one
    - a "tool"-call style object                   -> files_to_read from its path
    """
    out = dict(obj)
    cands = out.get("candidates")
    if isinstance(cands, dict):
        out["candidates"] = [cands]
    if not out.get("candidates"):
        if any(k in out for k in ("edits", "files", "patch")):
            cand: dict[str, Any] = {k: out.pop(k) for k in ("edits", "files", "patch") if k in out}
            cand.setdefault("rationale", str(out.get("rationale") or out.get("root_cause") or "candidate"))
            out["candidates"] = [cand]
        elif "tool" in out and isinstance(out.get("path"), str):
            out.setdefault("files_to_read", [out["path"]])
        else:
            file_like = {
                k: v
                for k, v in out.items()
                if isinstance(v, str)
                and isinstance(k, str)
                and ("/" in k or k.endswith((".py", ".ts", ".js", ".toml", ".cfg", ".txt", ".md")))
            }
            if file_like:
                paths = {p.rsplit("/", 1)[-1]: p for p in known_paths}
                files = [{"path": paths.get(k, k), "content": v} for k, v in file_like.items()]
                out = {k: v for k, v in out.items() if k not in file_like}
                out["candidates"] = [{"rationale": str(out.get("root_cause") or "full-file rewrite"), "files": files}]
    out.setdefault("root_cause", str(out.get("analysis") or out.get("explanation") or ""))
    if not isinstance(out.get("files_to_read"), list):
        out["files_to_read"] = []
    return out
