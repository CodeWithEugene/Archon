import { compareAttempts, isTerminalStatus } from "../lib/format";
import type { MissionEvent, MissionStatus, ModelUsage } from "../lib/types";
import type { MissionData } from "./types";

export const EMPTY_MISSION_DATA: MissionData = {
  missionId: null,
  mission: null,
  status: "PENDING" as MissionStatus,
  iteration: 0,
  reportedSpend: 0,
  connection: "idle",
  timeline: [],
  terminals: {},
  attemptOrder: [],
  activeTerminalTab: null,
  tests: {},
  patches: {},
  reviews: {},
  usageByModel: {},
  usageOrder: [],
  usageFromStream: false,
  selectedAttempt: null,
  diff: [],
  diffState: "idle",
  diffError: null,
  finished: false,
};

export interface UsageSlice {
  usageByModel: Record<string, ModelUsage>;
  usageOrder: string[];
}

/** Adds one usage record to the per-model totals, preserving first-seen order. */
export function mergeUsage(
  byModel: Record<string, ModelUsage>,
  order: string[],
  entry: ModelUsage,
): UsageSlice {
  const existing = byModel[entry.model];
  const merged: ModelUsage = existing
    ? {
        model: entry.model,
        prompt_tokens: existing.prompt_tokens + entry.prompt_tokens,
        completion_tokens: existing.completion_tokens + entry.completion_tokens,
        cost_usd: existing.cost_usd + entry.cost_usd,
      }
    : entry;
  return {
    usageByModel: { ...byModel, [entry.model]: merged },
    usageOrder: existing ? order : [...order, entry.model],
  };
}

/** Monotonic counter so terminal lines have stable React keys across tabs. */
let lineSeq = 0;

/** Pure state transition for one SSE frame. */
export function applyEventToState(
  state: MissionData,
  event: MissionEvent,
): Partial<MissionData> {
  const key = `${event.id}:${event.name}`;

  switch (event.name) {
    case "status":
      return {
        status: event.data.status,
        iteration: event.data.iteration,
        finished: isTerminalStatus(event.data.status),
        timeline: [...state.timeline, { key, kind: "status", data: event.data }],
      };

    case "thought":
      return {
        timeline: [
          ...state.timeline,
          { key, kind: "thought", data: event.data },
        ],
      };

    case "tavily":
      return {
        timeline: [...state.timeline, { key, kind: "tavily", data: event.data }],
      };

    case "error":
      return {
        timeline: [...state.timeline, { key, kind: "error", data: event.data }],
      };

    case "review":
      return {
        reviews: { ...state.reviews, [event.data.attempt]: event.data },
        selectedAttempt:
          event.data.verdict === "APPROVE"
            ? event.data.attempt
            : state.selectedAttempt,
        timeline: [...state.timeline, { key, kind: "review", data: event.data }],
      };

    case "terminal": {
      const attempt = event.data.attempt;
      const lines = state.terminals[attempt] ?? [];
      const known = state.attemptOrder.includes(attempt);
      lineSeq += 1;
      return {
        terminals: {
          ...state.terminals,
          [attempt]: [
            ...lines,
            { seq: lineSeq, stream: event.data.stream, line: event.data.line },
          ],
        },
        attemptOrder: known
          ? state.attemptOrder
          : [...state.attemptOrder, attempt].sort(compareAttempts),
        activeTerminalTab: state.activeTerminalTab ?? attempt,
      };
    }

    case "tests":
      return { tests: { ...state.tests, [event.data.attempt]: event.data } };

    case "patch": {
      const attempt = event.data.attempt;
      return {
        patches: { ...state.patches, [attempt]: event.data.files },
        attemptOrder: state.attemptOrder.includes(attempt)
          ? state.attemptOrder
          : [...state.attemptOrder, attempt].sort(compareAttempts),
      };
    }

    case "usage":
      // The first stream frame discards anything seeded from
      // `GET /missions/{id}`, so a reload that replays the whole event log
      // cannot double-count.
      return {
        ...(state.usageFromStream
          ? mergeUsage(state.usageByModel, state.usageOrder, event.data)
          : mergeUsage({}, [], event.data)),
        usageFromStream: true,
      };

    case "done":
      return {
        status: event.data.status,
        iteration: event.data.iterations,
        reportedSpend: Math.max(state.reportedSpend, event.data.spend_usd),
        finished: true,
        selectedAttempt:
          event.data.selected_attempt ?? state.selectedAttempt,
      };
  }
}
