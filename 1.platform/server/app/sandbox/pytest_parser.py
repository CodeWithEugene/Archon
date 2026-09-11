"""Parse test results. Prefers a JUnit XML report written inside the sandbox; falls back to pytest text."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # noqa: S405 - parsing our own sandbox-produced report

from app.core.models import TestReport

JUNIT_RELATIVE = "../archon-junit.xml"  # relative to the repo dir; resolves to /work/archon-junit.xml
JUNIT_ABSOLUTE = "/work/archon-junit.xml"

STATUS_LINE = re.compile(r"^(PASSED|FAILED|ERROR|XFAIL|XPASS|SKIPPED)\s+(\S+)", re.MULTILINE)
VERBOSE_LINE = re.compile(r"^(\S+::\S+)\s+(PASSED|FAILED|ERROR|XFAIL|XPASS|SKIPPED)\b", re.MULTILINE)
SUMMARY_LINE = re.compile(
    r"^(?:=+ )?((?:\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?)(?:, )?)+"
    r"(?: in [\d.]+s(?: \([^)]*\))?)?|no tests ran(?: in [\d.]+s)?)(?: =+)?\s*$",
    re.MULTILINE,
)
COUNT = re.compile(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed|deselected|warnings?)")
COLLECTION_ERROR = re.compile(r"^ERROR (?:collecting )?(\S+)", re.MULTILINE)


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def parse_junit(xml: bytes | str, exit_code: int) -> TestReport | None:
    """Parse a pytest JUnit report. Returns None when the document is not a JUnit report."""
    try:
        root = ET.fromstring(xml)  # noqa: S314
    except ET.ParseError:
        return None
    if root.tag not in {"testsuites", "testsuite"}:
        return None
    passed: dict[str, None] = {}
    failed: dict[str, None] = {}
    errors: dict[str, None] = {}
    for case in root.iter("testcase"):
        ident = _junit_id(case.get("classname", ""), case.get("name", ""), case.get("file"))
        if case.find("skipped") is not None:
            continue
        if case.find("error") is not None:
            errors.setdefault(ident, None)
        elif case.find("failure") is not None:
            failed.setdefault(ident, None)
        else:
            passed.setdefault(ident, None)
    # Collection errors appear as testcases named like the module with an <error> child and no classname.
    n = len(passed) + len(failed) + len(errors)
    summary = f"{len(failed)} failed, {len(passed)} passed" + (f", {len(errors)} errors" if errors else "")
    return TestReport(
        exit_code=exit_code,
        passed=sorted(passed),
        failed=sorted(failed),
        errors=sorted(errors),
        summary=summary,
        parsed=n > 0,
    )


def _junit_id(classname: str, name: str, file: str | None) -> str:
    """Build a pytest-style node id: path/to/test_mod.py::Class::test_name."""
    if file:
        path = file
        parts = classname.split(".")
        mod = file.rsplit("/", 1)[-1].removesuffix(".py")
        cls = parts[parts.index(mod) + 1 :] if mod in parts else []
    else:
        parts = classname.split(".")
        path = "/".join(parts[:1]) + ".py" if len(parts) == 1 else "/".join(parts[:-1]) + ".py"
        cls = []
        # Heuristic: last dotted part that starts uppercase is a class
        if len(parts) > 1 and parts[-1][:1].isupper():
            path = "/".join(parts[:-1]) + ".py"
            cls = [parts[-1]]
    return "::".join([path, *cls, name]) if name else path


def parse_pytest(output: str, exit_code: int) -> TestReport:
    text = strip_ansi(output)
    passed: dict[str, None] = {}
    failed: dict[str, None] = {}
    errors: dict[str, None] = {}

    for status, ident in STATUS_LINE.findall(text):
        _bucket(status, ident.split(" - ")[0], passed, failed, errors)
    if not (passed or failed or errors):
        for ident, status in VERBOSE_LINE.findall(text):
            _bucket(status, ident, passed, failed, errors)

    summaries = SUMMARY_LINE.findall(text)
    summary = summaries[-1].strip() if summaries else ""
    parsed = bool(passed or failed or errors)

    if not parsed:
        for ident in COLLECTION_ERROR.findall(text):
            errors.setdefault(ident, None)
        parsed = bool(errors)

    if summary:
        counts = {k: int(v) for v, k in COUNT.findall(summary)}
        n_pass = counts.get("passed", 0)
        n_fail = counts.get("failed", 0)
        n_err = counts.get("error", counts.get("errors", 0))
        # Fill in placeholders for buckets the text did not enumerate (e.g. PASSED lines hidden by -q).
        if len(passed) < n_pass:
            for i in range(len(passed), n_pass):
                passed.setdefault(f"<passed #{i + 1}>", None)
        if len(failed) < n_fail:
            for i in range(len(failed), n_fail):
                failed.setdefault(f"<failed #{i + 1}>", None)
        if len(errors) < n_err:
            for i in range(len(errors), n_err):
                errors.setdefault(f"<error #{i + 1}>", None)
        parsed = parsed or bool(counts)

    return TestReport(
        exit_code=exit_code,
        passed=sorted(passed),
        failed=sorted(failed),
        errors=sorted(errors),
        summary=summary,
        parsed=parsed,
    )


def _bucket(status: str, ident: str, passed: dict[str, None], failed: dict[str, None], errors: dict[str, None]) -> None:
    if status in {"PASSED", "XFAIL", "XPASS"}:
        passed.setdefault(ident, None)
    elif status == "FAILED":
        failed.setdefault(ident, None)
    elif status == "ERROR":
        errors.setdefault(ident, None)


def is_pytest_command(command: str) -> bool:
    """True when the command's final program is pytest (handles `. .venv/bin/activate && pytest -q`)."""
    last = command.strip().split("&&")[-1].strip().split(";")[-1].strip()
    head = last.split()
    if not head:
        return False
    exe = head[0]
    return exe == "pytest" or (exe.startswith("python") and "-m" in head and "pytest" in head)


def ensure_pytest_flags(command: str) -> str:
    """Append -rA and a JUnit report so per-test statuses are recoverable regardless of -q."""
    if not is_pytest_command(command):
        return command
    extra = []
    if "-rA" not in command and "-ra" not in command:
        extra.append("-rA")
    if "--junitxml" not in command:
        extra.append(f"--junitxml={JUNIT_RELATIVE}")
    return f"{command} {' '.join(extra)}".rstrip() if extra else command


def detect_libraries(output: str) -> list[str]:
    """Guess libraries involved from import paths in tracebacks (site-packages/<lib>/...)."""
    libs: dict[str, None] = {}
    for m in re.finditer(r"site-packages[/\\]([A-Za-z0-9_]+)[/\\]", output):
        name = m.group(1)
        if name not in {"_pytest", "pytest", "pluggy", "pkg_resources", "setuptools", "pip"}:
            libs.setdefault(name, None)
    for m in re.finditer(
        r"^(?:ImportError|ModuleNotFoundError): No module named '([A-Za-z0-9_]+)", output, re.MULTILINE
    ):
        libs.setdefault(m.group(1), None)
    return list(libs)[:5]


def failing_excerpt(output: str, limit: int = 20_000) -> str:
    """Trim output to the FAILURES/ERRORS sections plus the summary; fall back to the tail."""
    text = strip_ansi(output)
    start = text.find("= FAILURES =")
    if start == -1:
        start = text.find("= ERRORS =")
    if start != -1:
        text = text[max(0, start - 200) :]
    if len(text) > limit:
        text = text[-limit:]
    return text
