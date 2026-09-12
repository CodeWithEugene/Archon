"""Migration mission helpers: locate closed-provider call sites, map models, estimate cost."""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field

from app.core.pricing import CostEstimate, PriceTable
from app.core.router import Task
from app.llm.client import LLM, LLMError
from app.observability.tracing import traced
from app.sandbox.service import SandboxService

CALL_SITE_PATTERNS = [
    r"\bOpenAI\(",
    r"\bAsyncOpenAI\(",
    r"\bAnthropic\(",
    r"\bAsyncAnthropic\(",
    r"^\s*(from|import)\s+openai\b",
    r"^\s*(from|import)\s+anthropic\b",
    r"model\s*=\s*['\"]",
]
MODEL_LITERAL = re.compile(r"['\"]((?:gpt|o[1-9]|chatgpt|claude)[A-Za-z0-9._-]*)['\"]")
PATH_IN_RG = re.compile(r"^\.?/?([^:\s]+):\d+:", re.MULTILINE)


@dataclass
class MigrationScan:
    locations: str
    files: list[str]
    source_models: list[str]
    mapping: dict[str, str]
    estimates: list[CostEstimate] = field(default_factory=list)

    def summary(self) -> dict[str, object]:
        return {
            "files": self.files,
            "source_models": self.source_models,
            "mapping": self.mapping,
            "estimates": [e.__dict__ for e in self.estimates],
        }


@traced("migration.scan", run_type="tool")
async def scan_repository(sandbox: SandboxService, image_id: str, prices: PriceTable) -> MigrationScan:
    locations = await sandbox.search(image_id, CALL_SITE_PATTERNS)
    files: dict[str, None] = {}
    for m in PATH_IN_RG.finditer(locations):
        p = m.group(1)
        if not p.endswith((".lock", ".md", ".txt")):
            files.setdefault(p, None)
    models: dict[str, None] = {}
    for m in MODEL_LITERAL.finditer(locations):
        models.setdefault(m.group(1), None)
    mapping: dict[str, str] = {}
    estimates: list[CostEstimate] = []
    for src in models:
        target = prices.target_for(src)
        if target is None:
            # unknown literal: assume mid tier so the migration still proceeds
            target = prices.migration_map.get("mid", "nvidia/nemotron-3-super-120b-a12b")
        mapping[src] = target
        est = prices.estimate(src)
        if est is not None:
            estimates.append(est)
    return MigrationScan(
        locations=locations,
        files=list(files)[:8],
        source_models=list(models),
        mapping=mapping,
        estimates=estimates,
    )


@dataclass
class ParityResult:
    sampled: int
    mean_similarity: float
    per_prompt: list[dict[str, object]]
    note: str


@traced("migration.parity_sample")
async def run_parity_sample(sandbox: SandboxService, image_id: str, llm: LLM, *, limit: int = 8) -> ParityResult | None:
    """Model-level parity sample. Uses parity_prompts.json from the repository if present.

    This does not execute repository code. It sends each prompt input to the Nemotron tier the migration
    maps to and compares the answer with the recorded reference output. It is a signal, not proof.
    """
    raw = await sandbox.read_repo_file(image_id, "parity_prompts.json")
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    prompts = data if isinstance(data, list) else data.get("prompts", []) if isinstance(data, dict) else []
    rows: list[dict[str, object]] = []
    sims: list[float] = []
    for item in prompts[:limit]:
        if not isinstance(item, dict):
            continue
        inp = str(item.get("input", ""))
        ref = str(item.get("reference_output", ""))
        if not inp or not ref:
            continue
        try:
            comp = await llm.complete(
                Task.PARITY,
                [{"role": "system", "content": "Answer concisely."}, {"role": "user", "content": inp[:4000]}],
                max_tokens=300,
            )
            out = comp.text.strip()
        except LLMError as exc:
            out = f"<error: {exc}>"
        sim = difflib.SequenceMatcher(None, _norm(ref), _norm(out)).ratio()
        sims.append(sim)
        rows.append({"id": item.get("id"), "similarity": round(sim, 3), "reference": ref[:300], "output": out[:300]})
    if not rows:
        return None
    mean = sum(sims) / len(sims)
    return ParityResult(
        sampled=len(rows),
        mean_similarity=round(mean, 3),
        per_prompt=rows,
        note="Model-level sample against recorded references. Passing mocked tests does not prove behavioral parity.",
    )


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())
