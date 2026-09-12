"""Fetch SWE-bench Verified instance metadata from Hugging Face into tests/golden/swe/<instance_id>.json.

Usage:
  python -m tests.golden.fetch_swe psf__requests-1142 psf__requests-2317
  python -m tests.golden.fetch_swe --from-instances   # refresh every id listed in instances.json

Each file holds what the runner needs: the Sandboxes image tag, the test patch that adds the failing tests,
the FAIL_TO_PASS and PASS_TO_PASS ids, and the problem statement (used as the engineer's hint).
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
SWE_DIR = HERE / "swe"
INSTANCES = HERE / "instances.json"
DATASET = "princeton-nlp/SWE-bench_Verified"
WORKDIR = "/testbed"
# Some instances include network-bound tests that hang inside the sandbox. A per-test timeout keeps the
# run bounded; the plugin is installed on the fly (the sandbox has outbound network).
PYTEST_TIMEOUT_PREP = "(python -m pip install -q pytest-timeout >/dev/null 2>&1 || true) &&"
PYTEST_TIMEOUT_FLAGS = "--timeout=30 --timeout-method=signal"  # signal fails one test; thread kills pytest
ACTIVATE = (
    "source /opt/miniconda3/bin/activate && conda activate testbed"  # same as the SWE-bench harness; runs under bash
)


def image_tag(instance_id: str) -> str:
    """psf__requests-1142 -> swebench/sweb.eval.x86_64.psf_1776_requests-1142:latest"""
    owner, rest = instance_id.split("__", 1)
    return f"swebench/sweb.eval.x86_64.{owner}_1776_{rest}:latest"


def _get_json(url: str, attempts: int = 4) -> dict[str, object]:
    """The datasets-server API returns intermittent 500s; retry with backoff."""
    import time

    last: Exception | None = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:  # noqa: S310
                data: dict[str, object] = json.load(r)
                return data
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (i + 1))
    raise SystemExit(f"Hugging Face datasets-server unavailable after {attempts} attempts: {last}")


def _rows(instance_id: str) -> list[dict[str, object]]:
    base = "https://datasets-server.huggingface.co/"
    common = {"dataset": DATASET, "config": "default", "split": "test", "offset": 0, "length": 20}
    # Exact filter first, then full-text search as a fallback.
    flt = base + "filter?" + urllib.parse.urlencode({**common, "where": f"\"instance_id\"='{instance_id}'"})
    try:
        data = _get_json(flt, attempts=2)
        rows = [row["row"] for row in data.get("rows", [])]  # type: ignore[union-attr]
        if rows:
            return rows
    except SystemExit:
        pass
    data = _get_json(base + "search?" + urllib.parse.urlencode({**common, "query": instance_id}))
    return [row["row"] for row in data.get("rows", [])]  # type: ignore[union-attr]


def fetch(instance_id: str) -> dict[str, object]:
    rows = [r for r in _rows(instance_id) if r.get("instance_id") == instance_id]
    if not rows:
        raise SystemExit(f"{instance_id}: not found in {DATASET}")
    r = rows[0]
    f2p = json.loads(r["FAIL_TO_PASS"]) if isinstance(r["FAIL_TO_PASS"], str) else r["FAIL_TO_PASS"]
    p2p = json.loads(r["PASS_TO_PASS"]) if isinstance(r["PASS_TO_PASS"], str) else r["PASS_TO_PASS"]
    test_ids = [*f2p, *p2p]
    # Only the instance's own tests count, exactly like the SWE-bench harness. The dataset stores some
    # parametrized ids truncated at the first space ("...[test-test-Basic"); pytest aborts on unknown ids,
    # so those are left out of the command and matched by prefix when judging results.
    runnable = [t for t in test_ids if "[" not in t or t.endswith("]")]
    quoted = " ".join(f"'{t}'" for t in runnable)
    return {
        "id": instance_id,
        "repo": f"https://github.com/{r['repo']}",
        "base_commit": r["base_commit"],
        "image": image_tag(instance_id),
        "workdir": WORKDIR,
        "test_command": f"{ACTIVATE} && {PYTEST_TIMEOUT_PREP} pytest -q {PYTEST_TIMEOUT_FLAGS} {quoted}",
        "fail_to_pass": f2p,
        "pass_to_pass": p2p,
        "test_patch": r["test_patch"],
        "problem_statement": r["problem_statement"],
        "difficulty": r.get("difficulty", ""),
        "short_problem": str(r["problem_statement"]).strip().split("\n")[0][:200],
        "gold_patch_chars": len(r["patch"]),
        "dropped_truncated_ids": [t for t in test_ids if t not in runnable],
    }


def main(argv: list[str]) -> int:
    SWE_DIR.mkdir(exist_ok=True)
    ids = argv
    if ids == ["--from-instances"]:
        ids = json.loads(INSTANCES.read_text())["swe_bench_verified"]
    if not ids:
        print(__doc__)
        return 2
    for iid in ids:
        data = fetch(iid)
        (SWE_DIR / f"{iid}.json").write_text(json.dumps(data, indent=1))
        print(
            f"{iid}: f2p={len(data['fail_to_pass'])} p2p={len(data['pass_to_pass'])} {data['difficulty']} -> swe/{iid}.json"
        )
    inst = json.loads(INSTANCES.read_text()) if INSTANCES.exists() else {}
    listed = list(dict.fromkeys([*inst.get("swe_bench_verified", []), *ids]))
    inst["swe_bench_verified"] = listed
    INSTANCES.write_text(json.dumps(inst, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
