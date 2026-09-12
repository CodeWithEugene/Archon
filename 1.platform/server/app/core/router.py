"""Task-to-model routing across the Nemotron 3 tiers."""

from __future__ import annotations

from enum import StrEnum

from app.settings import Settings


class Task(StrEnum):
    DIAGNOSE_AND_PATCH = "diagnose_and_patch"
    MIGRATE = "migrate"
    RESEARCH_QUERIES = "research_queries"
    RESEARCH_BRIEF = "research_brief"
    REVIEW = "review"
    NARRATE = "narrate"
    COMPACT_LOGS = "compact_logs"
    PARSE_TESTS = "parse_tests"
    PARITY = "parity"


THINKING_TASKS = {Task.DIAGNOSE_AND_PATCH, Task.MIGRATE}


class ModelRouter:
    """Maps a task to a model id. Ultra is used only for patch synthesis."""

    def __init__(self, settings: Settings) -> None:
        self.ultra = settings.ultra_model
        self.super_ = settings.super_model
        self.nano = settings.nano_model
        self._table: dict[Task, str] = {
            Task.DIAGNOSE_AND_PATCH: self.ultra,
            Task.MIGRATE: self.ultra,
            Task.RESEARCH_QUERIES: self.super_,
            Task.RESEARCH_BRIEF: self.super_,
            Task.REVIEW: self.super_,
            Task.NARRATE: self.super_,
            Task.PARITY: self.super_,
            Task.COMPACT_LOGS: self.nano,
            Task.PARSE_TESTS: self.nano,
        }

    def model_for(self, task: Task) -> str:
        return self._table[task]

    def thinking_for(self, task: Task) -> bool:
        """Nemotron 3 reasons before answering. Keep that for patch synthesis; switch it off for cheap tasks."""
        return task in THINKING_TASKS

    def fallback_for(self, model: str) -> str | None:
        """If Ultra is unavailable, degrade to Super for that call. Nothing falls back further."""
        if model == self.ultra and self.ultra != self.super_:
            return self.super_
        return None

    def tier_of(self, model: str) -> str:
        if model == self.ultra:
            return "ULTRA"
        if model == self.super_:
            return "SUPER"
        if model == self.nano:
            return "NANO"
        return "OTHER"

    def as_dict(self) -> dict[str, str]:
        return {"ultra": self.ultra, "super": self.super_, "nano": self.nano}
