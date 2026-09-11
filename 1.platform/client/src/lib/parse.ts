/**
 * Boundary validation. Everything crossing the wire is `unknown` until it has
 * been through one of these coercions — the cockpit must never crash because
 * the orchestrator sent a null where a number was expected.
 */

import {
  MISSION_STATUSES,
  type MissionStatus,
  type MissionType,
  type TerminalStream,
  type ReviewVerdict,
} from "./types";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function asRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

export function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

export function nullableStr(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function num(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function bool(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

export function arr(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function strArray(value: unknown): string[] {
  return arr(value).filter((item): item is string => typeof item === "string");
}

export function missionStatus(
  value: unknown,
  fallback: MissionStatus = "PENDING",
): MissionStatus {
  const found = MISSION_STATUSES.find((status) => status === value);
  return found ?? fallback;
}

export function missionType(
  value: unknown,
  fallback: MissionType = "BUG_HEALING",
): MissionType {
  return value === "MIGRATION" || value === "BUG_HEALING" ? value : fallback;
}

export function terminalStream(value: unknown): TerminalStream {
  return value === "stderr" || value === "cmd" ? value : "stdout";
}

export function reviewVerdict(value: unknown): ReviewVerdict {
  return value === "REJECT" ? "REJECT" : "APPROVE";
}

/** `JSON.parse` that yields `unknown` instead of `any`, and never throws. */
export function parseJson(raw: string): unknown {
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return null;
  }
}
