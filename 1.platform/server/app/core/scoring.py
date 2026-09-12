"""Attempt scoring against the baseline: fail-to-pass and pass-to-pass."""

from __future__ import annotations

from app.core.models import Attempt, TestReport


def matches_any(test_id: str, ids: set[str]) -> bool:
    """SWE-bench stores some parametrized ids truncated at the first space, so match on prefix too."""
    return test_id in ids or any(test_id.startswith(i) for i in ids)


def select(ids: set[str], dataset_ids: set[str] | None) -> set[str]:
    """Restrict a set of observed test ids to those the dataset names (prefix-aware). None keeps all."""
    if dataset_ids is None:
        return ids
    return {t for t in ids if matches_any(t, dataset_ids)}


def score_attempt(
    baseline: TestReport,
    attempt: Attempt,
    targets: set[str] | None = None,
    protected: set[str] | None = None,
) -> Attempt:
    """Fill fail_to_pass and pass_to_pass_broken on the attempt from its report.

    `targets` / `protected` are the instance's FAIL_TO_PASS / PASS_TO_PASS ids when known (SWE-bench);
    otherwise every test that failed at baseline is a target and every test that passed is protected.
    """
    report = attempt.report
    if report is None or not attempt.applied:
        attempt.fail_to_pass = 0
        attempt.pass_to_pass_broken = len(baseline.passed) if baseline.passed else 1
        return attempt
    base_fail = select(baseline.failing, targets)
    base_pass = select(set(baseline.passed), protected)
    now_pass = set(report.passed)
    now_fail = report.failing
    if baseline.parsed and report.parsed and not _placeholder(baseline) and not _placeholder(report):
        attempt.fail_to_pass = len(base_fail & now_pass)
        attempt.pass_to_pass_broken = len(base_pass & now_fail)
    else:
        # Count-only fallback when per-test ids are unavailable.
        attempt.fail_to_pass = max(0, len(base_fail) - len(now_fail)) if report.exit_code == 0 else 0
        attempt.pass_to_pass_broken = 0 if report.exit_code == 0 else max(0, len(now_fail) - len(base_fail))
        if report.exit_code != 0 and attempt.fail_to_pass == 0 and len(now_fail) >= len(base_fail):
            attempt.pass_to_pass_broken = max(attempt.pass_to_pass_broken, 0)
    return attempt


def _placeholder(report: TestReport) -> bool:
    return any(t.startswith("<") for t in [*report.passed, *report.failed, *report.errors])


def attempt_key(a: Attempt) -> tuple[int, int, int]:
    """Higher is better. Regression-free first, then most fixed, then smallest patch."""
    return (1 if a.pass_to_pass_broken == 0 and a.applied else 0, a.fail_to_pass, -a.patch_lines)


def best_attempt(attempts: list[Attempt]) -> Attempt | None:
    if not attempts:
        return None
    return max(attempts, key=attempt_key)


def is_resolved(
    baseline: TestReport,
    attempt: Attempt,
    targets: set[str] | None = None,
    protected: set[str] | None = None,
) -> bool:
    """Every target test passes, no protected test broke, and (without instance ids) the run exited 0."""
    if not attempt.applied or attempt.report is None:
        return False
    if attempt.pass_to_pass_broken != 0:
        return False
    if baseline.parsed and attempt.report.parsed and not _placeholder(baseline) and not _placeholder(attempt.report):
        wanted = select(baseline.failing, targets)
        if targets is not None:
            # Instance-scoped judgement: unrelated failures in the same files do not block resolution.
            return bool(wanted) and wanted <= set(attempt.report.passed)
        return attempt.report.exit_code == 0 and wanted <= set(attempt.report.passed)
    return attempt.report.exit_code == 0
