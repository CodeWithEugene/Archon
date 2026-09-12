"""Unified-diff inspection: touched files, size, and deterministic safety checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

FILE_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.MULTILINE)
MINUS_HEADER = re.compile(r"^--- (?:a/)?(\S+)", re.MULTILINE)
PLUS_HEADER = re.compile(r"^\+\+\+ (?:b/)?(\S+)", re.MULTILINE)
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
TEST_PATH = re.compile(
    r"(^|/)(tests?|spec|__tests__)(/|$)|(^|/)test_[^/]+\.py$|_test\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$"
)
WEAKENING = re.compile(
    r"^\+\s*(?:@pytest\.mark\.(?:skip|xfail)|pytest\.skip\(|@unittest\.skip|it\.skip\(|test\.skip\(|xit\()",
    re.MULTILINE,
)
DELETED_TEST_DEF = re.compile(r"^-\s*(?:def test_|async def test_|it\(|test\()", re.MULTILINE)


class EditError(ValueError):
    pass


def apply_edits(original: str, edits: list[tuple[str, str]], path: str = "") -> str:
    """Apply (search, replace) pairs in order. Each search must match exactly once.

    A second pass tolerates trailing-whitespace differences per line, which is the most common
    model transcription error. Anything looser than that is refused so the model gets a precise report.
    """
    text = original
    for i, (search, replace) in enumerate(edits, 1):
        if not search:
            raise EditError(f"{path}: edit {i} has an empty search block")
        count = text.count(search)
        if count == 1:
            text = text.replace(search, replace, 1)
            continue
        if count > 1:
            raise EditError(
                f"{path}: edit {i} search block matches {count} places; include more context to make it unique"
            )
        norm_text = "\n".join(line.rstrip() for line in text.split("\n"))
        norm_search = "\n".join(line.rstrip() for line in search.split("\n"))
        if norm_search and norm_text.count(norm_search) == 1:
            start = norm_text.index(norm_search)
            # Map the normalized span back to the original by line numbers.
            pre_lines = norm_text[:start].count("\n")
            n_lines = norm_search.count("\n") + 1
            lines = text.split("\n")
            lines[pre_lines : pre_lines + n_lines] = replace.split("\n")
            text = "\n".join(lines)
            continue
        first = search.strip().split("\n")[0].strip()[:80]
        lines = text.split("\n")
        hint = ""
        anchor: int | None = None
        if first:
            for ln, line in enumerate(lines, 1):
                if first in line:
                    anchor = ln
                    break
        if anchor is not None:
            a, b = max(1, anchor - 2), min(len(lines), anchor + 14)
            real = "\n".join(f"{n:5d}| {lines[n - 1]}" for n in range(a, b + 1))
            hint = (
                f" The first search line appears at line {anchor} but the following lines differ from the file."
                f" The file actually reads:\n{real}"
            )
        else:
            head = "\n".join(f"{n:5d}| {lines[n - 1]}" for n in range(1, min(len(lines), 30) + 1))
            hint = f" The first search line does not appear anywhere in the file. The file begins:\n{head}"
        raise EditError(
            f"{path}: edit {i} search block not found.{hint}\n"
            "Copy the search text verbatim from the file; do not paraphrase or invent fields."
        )
    return text


@dataclass
class PatchInfo:
    files: list[str]
    added: int
    removed: int
    per_file: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def lines(self) -> int:
        return self.added + self.removed


@dataclass
class SafetyReport:
    ok: bool
    problems: list[str]


def inspect_patch(patch: str) -> PatchInfo:
    files: dict[str, None] = {}
    for _, b in FILE_HEADER.findall(patch):
        files.setdefault(b, None)
    if not files:
        for p in PLUS_HEADER.findall(patch):
            if p != "/dev/null":
                files.setdefault(p, None)
        for p in MINUS_HEADER.findall(patch):
            if p != "/dev/null":
                files.setdefault(p, None)
    per_file: dict[str, tuple[int, int]] = {}
    current: str | None = None
    added = removed = 0
    for line in patch.splitlines():
        if line.startswith("+++ "):
            name = line[4:].strip()
            current = name[2:] if name.startswith("b/") else name
            per_file.setdefault(current, (0, 0))
            continue
        if line.startswith(("--- ", "diff --git", "index ", "@@")):
            continue
        if line.startswith("+"):
            added += 1
            if current:
                a, r = per_file[current]
                per_file[current] = (a + 1, r)
        elif line.startswith("-"):
            removed += 1
            if current:
                a, r = per_file[current]
                per_file[current] = (a, r + 1)
    return PatchInfo(files=list(files), added=added, removed=removed, per_file=per_file)


def normalize_patch(patch: str) -> str:
    """Make model output applyable: strip fences, ensure trailing newline, normalize line endings."""
    text = patch.replace("\r\n", "\n").strip("\n")
    fence = re.search(r"```(?:diff|patch)?\n(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip("\n")
    start = text.find("diff --git")
    if start == -1:
        start = text.find("--- ")
    if start > 0:
        text = text[start:]
    return text + "\n"


def check_patch_safety(patch: str, *, allow_test_edits: bool = True, max_lines: int = 1500) -> SafetyReport:
    problems: list[str] = []
    info = inspect_patch(patch)
    if not info.files:
        problems.append("patch touches no recognizable files")
    for f in info.files:
        if f.startswith("/") or f.startswith("../") or "/../" in f:
            problems.append(f"path escapes repository: {f}")
        if f.startswith(".git/"):
            problems.append(f"patch modifies git metadata: {f}")
    if info.lines > max_lines:
        problems.append(f"patch is too large: {info.lines} changed lines (limit {max_lines})")
    for pat in SECRET_PATTERNS:
        if pat.search(patch):
            problems.append("patch contains a credential-like string")
            break
    if WEAKENING.search(patch):
        problems.append("patch adds skip or xfail markers to tests")
    if DELETED_TEST_DEF.search(patch):
        problems.append("patch deletes a test function")
    if not allow_test_edits:
        for f in info.files:
            if TEST_PATH.search(f):
                problems.append(f"patch edits a test file: {f}")
    for m in re.finditer(r"^\+\+\+ /dev/null", patch, re.MULTILINE):
        # a file deletion; find its --- header
        before = patch[: m.start()].rsplit("--- ", 1)
        if len(before) == 2:
            name = before[1].split("\n", 1)[0].strip()
            name = name[2:] if name.startswith("a/") else name
            if TEST_PATH.search(name):
                problems.append(f"patch deletes test file: {name}")
    return SafetyReport(ok=not problems, problems=problems)
