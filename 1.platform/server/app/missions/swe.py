"""SWE-bench Verified instance catalog. Instances live in tests/golden/swe/<id>.json (see tests/golden/fetch_swe.py)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SweInstance:
    id: str
    repo: str
    image: str
    test_command: str
    workdir: str = "/testbed"
    short_problem: str = ""
    problem_statement: str = ""
    test_patch: str = ""
    fail_to_pass: tuple[str, ...] = ()
    pass_to_pass: tuple[str, ...] = ()
    difficulty: str = ""
    base_commit: str = ""
    extra: dict[str, object] = field(default_factory=dict, compare=False)


class SweCatalog:
    def __init__(self, instances: list[SweInstance]) -> None:
        self._by_id = {i.id: i for i in instances}

    @classmethod
    def load(cls, path: Path) -> SweCatalog:
        """`path` is instances.json; instance files are read from the sibling `swe/` directory."""
        if not path.exists():
            return cls([])
        data = json.loads(path.read_text(encoding="utf-8"))
        ids = data.get("swe_bench_verified", []) if isinstance(data, dict) else []
        swe_dir = path.parent / "swe"
        out: list[SweInstance] = []
        for iid in ids:
            f = swe_dir / f"{iid}.json"
            if not f.exists():
                continue
            raw = json.loads(f.read_text(encoding="utf-8"))
            out.append(
                SweInstance(
                    id=str(raw["id"]),
                    repo=str(raw.get("repo", "")),
                    image=str(raw["image"]),
                    test_command=str(raw["test_command"]),
                    workdir=str(raw.get("workdir", "/testbed")),
                    short_problem=str(raw.get("short_problem", ""))[:300],
                    problem_statement=str(raw.get("problem_statement", "")),
                    test_patch=str(raw.get("test_patch", "")),
                    fail_to_pass=tuple(str(t) for t in raw.get("fail_to_pass", [])),
                    pass_to_pass=tuple(str(t) for t in raw.get("pass_to_pass", [])),
                    difficulty=str(raw.get("difficulty", "")),
                    base_commit=str(raw.get("base_commit", "")),
                )
            )
        return cls(out)

    def get(self, instance_id: str) -> SweInstance | None:
        return self._by_id.get(instance_id)

    def list(self) -> list[dict[str, str]]:
        return [
            {"id": i.id, "repo": i.repo, "short_problem": i.short_problem, "difficulty": i.difficulty}
            for i in self._by_id.values()
        ]
