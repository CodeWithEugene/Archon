import type { MissionStatus } from "@/lib/types";

const TONE: Record<MissionStatus, string> = {
  PENDING: "border-line-strong text-muted",
  PROVISIONING: "border-info/50 text-info",
  REPRODUCING: "border-info/50 text-info",
  GROUNDING: "border-nano/50 text-nano",
  REASONING: "border-accent/60 text-accent",
  TESTING: "border-warn/50 text-warn",
  REVIEWING: "border-warn/50 text-warn",
  VERIFIED: "border-ok/60 text-ok",
  NOTHING_TO_FIX: "border-ok/40 text-ok",
  FAILED: "border-bad/60 text-bad",
  ABORTED: "border-bad/40 text-bad",
};

const ACTIVE: readonly MissionStatus[] = [
  "PENDING",
  "PROVISIONING",
  "REPRODUCING",
  "GROUNDING",
  "REASONING",
  "TESTING",
  "REVIEWING",
];

export function StatusPill({
  status,
  size = "md",
}: {
  status: MissionStatus;
  size?: "sm" | "md";
}) {
  const running = ACTIVE.includes(status);
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-sm border bg-bg/60 font-mono uppercase tracking-[0.14em] ${TONE[status]} ${
        size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]"
      }`}
      role="status"
      aria-label={`Mission status: ${status.replace(/_/g, " ").toLowerCase()}`}
    >
      <span
        aria-hidden
        className={`size-1.5 rounded-full bg-current ${running ? "archon-live-dot" : ""}`}
      />
      {status.replace(/_/g, " ")}
    </span>
  );
}
