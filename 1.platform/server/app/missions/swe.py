"""SWE-bench Verified instance catalog backed by tests/golden/instances.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SweInstance:
    id: str
    repo: str
    image: str
    test_command: str
    short_problem: str
    fail_to_pass: tuple[str, ...] = ()


class SweCatalog:
    def __init__(self, instances: list[SweInstance]) -> None:
        self._by_id = {i.id: i for i in instances}

    @classmethod
    def load(cls, path: Path) -> SweCatalog:
        if not path.exists():
            return cls([])
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("swe_bench_verified", []) if isinstance(data, dict) else []
        out: list[SweInstance] = []
        for item in raw:
            if isinstance(item, dict) and "id" in item and "image" in item:
                out.append(
                    SweInstance(
                        id=str(item["id"]),
                        repo=str(item.get("repo", "")),
                        image=str(item["image"]),
                        test_command=str(item.get("test_command", "pytest -q")),
                        short_problem=str(item.get("short_problem", ""))[:300],
                        fail_to_pass=tuple(str(t) for t in item.get("fail_to_pass", [])),
                    )
                )
        return cls(out)

    def get(self, instance_id: str) -> SweInstance | None:
        return self._by_id.get(instance_id)

    def list(self) -> list[dict[str, str]]:
        return [{"id": i.id, "repo": i.repo, "short_problem": i.short_problem} for i in self._by_id.values()]
