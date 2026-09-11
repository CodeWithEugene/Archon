import type {
  ConnectionState,
  DiffFile,
  ErrorEventData,
  Mission,
  MissionStatus,
  ModelUsage,
  PatchFileStat,
  ReviewEventData,
  StatusEventData,
  TavilyEventData,
  TerminalStream,
  TestsEventData,
  ThoughtEventData,
} from "../lib/types";

export type TimelineEntry =
  | { key: string; kind: "status"; data: StatusEventData }
  | { key: string; kind: "thought"; data: ThoughtEventData }
  | { key: string; kind: "tavily"; data: TavilyEventData }
  | { key: string; kind: "review"; data: ReviewEventData }
  | { key: string; kind: "error"; data: ErrorEventData };

export interface TerminalLine {
  seq: number;
  stream: TerminalStream;
  line: string;
}

export type DiffState = "idle" | "loading" | "ready" | "error";

/** Everything the cockpit renders. Actions live on the store itself. */
export interface MissionData {
  missionId: string | null;
  mission: Mission | null;
  status: MissionStatus;
  iteration: number;
  reportedSpend: number;
  connection: ConnectionState;

  timeline: TimelineEntry[];
  terminals: Record<string, TerminalLine[]>;
  attemptOrder: string[];
  activeTerminalTab: string | null;
  tests: Record<string, TestsEventData>;
  patches: Record<string, PatchFileStat[]>;
  reviews: Record<string, ReviewEventData>;

  usageByModel: Record<string, ModelUsage>;
  usageOrder: string[];
  /** True once a `usage` SSE frame has arrived; the stream then owns the totals. */
  usageFromStream: boolean;

  selectedAttempt: string | null;
  diff: DiffFile[];
  diffState: DiffState;
  diffError: string | null;

  finished: boolean;
}
