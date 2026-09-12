"""Engineer: Nemotron 3 Ultra produces a root-cause note and candidate patches."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import cast

from pydantic import ValidationError

from app.core.models import Attempt, EngineerOutput
from app.core.patches import normalize_patch
from app.core.router import Task
from app.llm.client import LLM, LLMError
from app.llm.prompts import engineer_messages, migration_messages
from app.observability.tracing import traced
from app.sandbox.service import SandboxService

MAX_READ_ROUNDS = 3


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
            try:
                out = EngineerOutput.model_validate(obj)
            except ValidationError as exc:
                last_error = _short(exc)
                continue
            if out.candidates:
                for c in out.candidates:
                    if c.patch and not c.uses_edits:
                        c.patch = normalize_patch(c.patch)
                return out
            wanted = [p for p in out.files_to_read if p not in excerpts]
            if not wanted:
                last_error = "you asked to read files you already have; propose candidates now"
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
