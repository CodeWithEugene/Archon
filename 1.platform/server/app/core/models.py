"""Domain models shared by the API, the runner, and the store."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class MissionType(StrEnum):
    BUG_HEALING = "BUG_HEALING"
    MIGRATION = "MIGRATION"


class MissionStatus(StrEnum):
    PENDING = "PENDING"
    PROVISIONING = "PROVISIONING"
    REPRODUCING = "REPRODUCING"
    GROUNDING = "GROUNDING"
    REASONING = "REASONING"
    TESTING = "TESTING"
    REVIEWING = "REVIEWING"
    VERIFIED = "VERIFIED"
    NOTHING_TO_FIX = "NOTHING_TO_FIX"
    FAILED = "FAILED"
    ABORTED = "ABORTED"

    @property
    def terminal(self) -> bool:
        return self in {
            MissionStatus.VERIFIED,
            MissionStatus.NOTHING_TO_FIX,
            MissionStatus.FAILED,
            MissionStatus.ABORTED,
        }


class EventKind(StrEnum):
    STATUS = "status"
    THOUGHT = "thought"
    TAVILY = "tavily"
    TERMINAL = "terminal"
    TESTS = "tests"
    PATCH = "patch"
    REVIEW = "review"
    USAGE = "usage"
    ERROR = "error"
    DONE = "done"


GITHUB_URL = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?/?$")
GIT_REF = re.compile(r"^[A-Za-z0-9_./-]{1,100}$")


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def utcnow() -> datetime:
    return datetime.now(UTC)


class MissionCreate(BaseModel):
    type: MissionType
    repo_url: str | None = None
    git_ref: str = "main"
    test_command: str | None = None
    install_command: str | None = None
    swe_instance_id: str | None = None
    hint: str | None = Field(default=None, max_length=20_000)

    @field_validator("git_ref")
    @classmethod
    def _ref(cls, v: str) -> str:
        if not GIT_REF.match(v) or ".." in v or v.startswith("-"):
            raise ValueError("invalid git ref")
        return v

    @field_validator("test_command", "install_command")
    @classmethod
    def _cmd(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v or len(v) > 500 or "\n" in v:
            raise ValueError("command must be a single non-empty line under 500 characters")
        return v

    @model_validator(mode="after")
    def _target(self) -> MissionCreate:
        if bool(self.repo_url) == bool(self.swe_instance_id):
            raise ValueError("provide exactly one of repo_url or swe_instance_id")
        if self.repo_url and not self.test_command:
            raise ValueError("test_command is required with repo_url")
        return self


def validate_repo_url(url: str, allow_local: bool) -> str:
    url = url.strip()
    if GITHUB_URL.match(url):
        return url.removesuffix("/")
    if allow_local and url.startswith("file://") and ".." not in url:
        return url
    raise ValueError("repo_url must be a public https://github.com/<owner>/<repo> URL")


class TestReport(BaseModel):
    __test__ = False  # not a pytest test class

    exit_code: int
    passed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    summary: str = ""
    parsed: bool = True

    @property
    def total(self) -> int:
        return len(self.passed) + len(self.failed) + len(self.errors)

    @property
    def failing(self) -> set[str]:
        return set(self.failed) | set(self.errors)


class FileEdit(BaseModel):
    """Exact search-and-replace on one file. `search` must be copied verbatim from the source and be unique."""

    path: str = Field(min_length=1, max_length=400)
    search: str = Field(min_length=1, max_length=20_000)
    replace: str = Field(max_length=40_000)


class FileContent(BaseModel):
    """Full replacement content for a small or new file."""

    path: str = Field(min_length=1, max_length=400)
    content: str = Field(max_length=200_000)


class Candidate(BaseModel):
    rationale: str = Field(max_length=2000)
    edits: list[FileEdit] = Field(default_factory=list, max_length=40)
    files: list[FileContent] = Field(default_factory=list, max_length=10)
    patch: str = Field(default="", max_length=200_000)

    @model_validator(mode="after")
    def _has_change(self) -> Candidate:
        if not self.edits and not self.files and len(self.patch.strip()) < 10:
            raise ValueError("candidate needs edits, files, or a unified diff patch")
        return self

    @property
    def uses_edits(self) -> bool:
        return bool(self.edits or self.files)


class EngineerOutput(BaseModel):
    root_cause: str = Field(default="", max_length=6000)
    files_to_read: list[str] = Field(default_factory=list, max_length=8)
    candidates: list[Candidate] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def _one_of(self) -> EngineerOutput:
        if not self.candidates and not self.files_to_read:
            raise ValueError("engineer must return candidates or files_to_read")
        return self


class ReviewOutput(BaseModel):
    verdict: str
    reasons: list[str] = Field(default_factory=list)

    @field_validator("verdict")
    @classmethod
    def _verdict(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in {"APPROVE", "REJECT"}:
            raise ValueError("verdict must be APPROVE or REJECT")
        return v


class Attempt(BaseModel):
    id: str
    mission_id: str
    iteration: int
    parent_image: str
    result_image: str | None = None
    patch: str
    rationale: str = ""
    exit_code: int | None = None
    fail_to_pass: int = 0
    pass_to_pass_broken: int = 0
    patch_lines: int = 0
    applied: bool = False
    selected: bool = False
    report: TestReport | None = None
    report_output: str | None = None
    error: str | None = None


class ModelUsage(BaseModel):
    mission_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    task: str = ""


class Event(BaseModel):
    id: int
    mission_id: str
    kind: EventKind
    payload: dict[str, Any]
    ts: datetime = Field(default_factory=utcnow)


class DiffFile(BaseModel):
    path: str
    original: str
    modified: str
    language: str = "plaintext"


class Mission(BaseModel):
    id: str
    type: MissionType
    repo_url: str | None
    git_ref: str
    test_command: str | None
    install_command: str | None = None
    swe_instance_id: str | None
    hint: str | None = None
    status: MissionStatus = MissionStatus.PENDING
    iteration: int = 0
    spend_usd: float = 0.0
    baseline_image: str | None = None
    baseline_report: TestReport | None = None
    selected_attempt: str | None = None
    failure_report: str | None = None
    replay_of: str | None = None
    diff: list[DiffFile] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None

    @property
    def is_replay(self) -> bool:
        return self.id.startswith("rp_")


class MissionDetail(Mission):
    attempts: list[Attempt] = Field(default_factory=list)
    usage: list[ModelUsage] = Field(default_factory=list)
