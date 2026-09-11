import { modelTier, shortModelName } from "@/lib/format";
import type { ModelTier } from "@/lib/types";

const TONE: Record<ModelTier, string> = {
  ULTRA: "border-accent/60 text-accent bg-accent/10",
  SUPER: "border-info/60 text-info bg-info/10",
  NANO: "border-nano/60 text-nano bg-nano/10",
  MODEL: "border-line-strong text-muted bg-panel-alt",
};

export function ModelBadge({ model }: { model: string }) {
  const tier = modelTier(model);
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-sm border px-1.5 py-px font-mono text-[10px] font-medium tracking-[0.16em] ${TONE[tier]}`}
      title={model || "unknown model"}
    >
      {model === "archon" ? "ARCHON" : tier}
    </span>
  );
}

export function ModelName({ model }: { model: string }) {
  return (
    <span className="font-mono text-[11px] text-faint">
      {shortModelName(model)}
    </span>
  );
}
