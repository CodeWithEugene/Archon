"""Price table loading, per-call cost accounting, and migration cost estimates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelPrice:
    input_per_m: float
    output_per_m: float
    provider: str
    tier: str
    verified: bool


@dataclass(frozen=True)
class CostEstimate:
    source_model: str
    target_model: str
    source_blended_per_m: float
    target_blended_per_m: float
    monthly_tokens: int
    source_monthly_usd: float
    target_monthly_usd: float
    reduction_pct: float


class PriceTable:
    def __init__(self, data: dict[str, object]) -> None:
        self.updated: str = str(data.get("updated", "unknown"))
        ratio = data.get("assumed_input_output_ratio", [3, 1])
        if not isinstance(ratio, list) or len(ratio) != 2:
            raise ValueError("assumed_input_output_ratio must be a 2-item list")
        self.ratio: tuple[float, float] = (float(ratio[0]), float(ratio[1]))
        models = data.get("models", {})
        if not isinstance(models, dict):
            raise ValueError("models must be an object")
        self.models: dict[str, ModelPrice] = {}
        for name, m in models.items():
            if not isinstance(m, dict):
                raise ValueError(f"model entry {name} must be an object")
            self.models[name] = ModelPrice(
                input_per_m=float(m["input"]),
                output_per_m=float(m["output"]),
                provider=str(m.get("provider", "unknown")),
                tier=str(m.get("tier", "mid")),
                verified=bool(m.get("verified", False)),
            )
        mm = data.get("migration_map", {})
        self.migration_map: dict[str, str] = {str(k): str(v) for k, v in mm.items()} if isinstance(mm, dict) else {}
        al = data.get("aliases", {})
        self.aliases: dict[str, str] = {str(k): str(v) for k, v in al.items()} if isinstance(al, dict) else {}
        src = data.get("sources")
        self.sources: dict[str, str] = {str(k): str(v) for k, v in src.items()} if isinstance(src, dict) else {}

    @classmethod
    def load(cls, path: Path) -> PriceTable:
        with path.open("r", encoding="utf-8") as fh:
            return cls(json.load(fh))

    def resolve(self, model: str) -> str:
        """Map a possibly-aliased or dated model name to a priced entry, or return it unchanged."""
        if model in self.models:
            return model
        if model in self.aliases:
            return self.aliases[model]
        # strip date suffixes like -2025-08-07 or @latest
        base = model.split("@")[0]
        parts = base.rsplit("-", 3)
        for i in range(1, 4):
            cand = "-".join(parts[:-i]) if len(parts) > i else None
            if cand and cand in self.models:
                return cand
        for name in self.models:
            if base.startswith(name):
                return name
        return model

    def price(self, model: str) -> ModelPrice | None:
        return self.models.get(self.resolve(model))

    def cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        p = self.price(model)
        if p is None:
            return 0.0
        return (prompt_tokens * p.input_per_m + completion_tokens * p.output_per_m) / 1_000_000

    def blended_per_m(self, model: str) -> float | None:
        p = self.price(model)
        if p is None:
            return None
        i, o = self.ratio
        return (p.input_per_m * i + p.output_per_m * o) / (i + o)

    def target_for(self, source_model: str) -> str | None:
        p = self.price(source_model)
        if p is None:
            return None
        return self.migration_map.get(p.tier)

    def estimate(self, source_model: str, monthly_tokens: int = 100_000_000) -> CostEstimate | None:
        target = self.target_for(source_model)
        if target is None:
            return None
        s = self.blended_per_m(source_model)
        t = self.blended_per_m(target)
        if s is None or t is None or s <= 0:
            return None
        s_month = s * monthly_tokens / 1_000_000
        t_month = t * monthly_tokens / 1_000_000
        return CostEstimate(
            source_model=self.resolve(source_model),
            target_model=target,
            source_blended_per_m=round(s, 4),
            target_blended_per_m=round(t, 4),
            monthly_tokens=monthly_tokens,
            source_monthly_usd=round(s_month, 2),
            target_monthly_usd=round(t_month, 2),
            reduction_pct=round((1 - t / s) * 100, 1),
        )
