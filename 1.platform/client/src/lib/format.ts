import {
  REPLAY_ID_PREFIX,
  TERMINAL_STATUSES,
  type MissionStatus,
  type ModelTier,
} from "./types";

/**
 * Model badge tier, derived from the Token Factory model id — the server sends
 * ids like `nvidia/nemotron-3-ultra-550b-a55b`, never a tier field.
 */
export function modelTier(modelId: string): ModelTier {
  const id = modelId.toLowerCase();
  if (id.includes("ultra")) return "ULTRA";
  if (id.includes("super")) return "SUPER";
  if (id.includes("nano")) return "NANO";
  return "MODEL";
}

/** Trims the vendor prefix for display: `nvidia/nemotron-3-nano-30b` -> `nemotron-3-nano-30b`. */
export function shortModelName(modelId: string): string {
  const slash = modelId.lastIndexOf("/");
  return slash >= 0 ? modelId.slice(slash + 1) : modelId;
}

export function isReplayMission(missionId: string): boolean {
  return missionId.startsWith(REPLAY_ID_PREFIX);
}

export function isTerminalStatus(status: MissionStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export function formatUsd(value: number): string {
  if (!Number.isFinite(value)) return "$0.00";
  return value >= 10 ? `$${value.toFixed(2)}` : `$${value.toFixed(3)}`;
}

export function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return String(value);
}

export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}

/** `https://github.com/owner/repo` -> `owner/repo`. */
export function shortRepo(repoUrl: string | null): string | null {
  if (!repoUrl) return null;
  const match = /github\.com\/([^/]+\/[^/]+?)(?:\.git)?\/?$/.exec(repoUrl);
  return match ? match[1] : repoUrl;
}

/** Human label for an attempt tab. `baseline` is the pre-patch test run. */
export function attemptLabel(attempt: string): string {
  return attempt === "baseline" ? "baseline" : attempt;
}

/** Baseline always sorts first; the rest keep their natural id order. */
export function compareAttempts(a: string, b: string): number {
  if (a === b) return 0;
  if (a === "baseline") return -1;
  if (b === "baseline") return 1;
  return a.localeCompare(b);
}
