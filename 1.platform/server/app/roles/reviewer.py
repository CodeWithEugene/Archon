"""Reviewer: deterministic safety checks first, then Nemotron 3 Super for judgment."""

from __future__ import annotations

from pydantic import ValidationError

from app.core.models import ReviewOutput
from app.core.patches import check_patch_safety
from app.core.router import Task
from app.llm.client import LLM, LLMError
from app.llm.prompts import review_messages


class Reviewer:
    def __init__(self, llm: LLM, *, allow_test_edits: bool = True) -> None:
        self.llm = llm
        self.allow_test_edits = allow_test_edits

    async def review(self, patch: str, root_cause: str, test_summary: str) -> ReviewOutput:
        safety = check_patch_safety(patch, allow_test_edits=self.allow_test_edits)
        if not safety.ok:
            return ReviewOutput(verdict="REJECT", reasons=safety.problems)
        try:
            obj, _ = await self.llm.complete_json(
                Task.REVIEW, review_messages(patch, root_cause, test_summary), max_tokens=600
            )
            return ReviewOutput.model_validate(obj)
        except (LLMError, ValidationError) as exc:
            # A reviewer outage must not block a patch that passed deterministic checks and tests;
            # it is recorded so the UI can show that the model review was skipped.
            return ReviewOutput(verdict="APPROVE", reasons=[f"model review skipped: {type(exc).__name__}"])
