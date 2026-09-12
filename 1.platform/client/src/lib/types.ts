/** Wire types for the ARCHON orchestrator (FastAPI). Kept in sync with DESIGN.md §5. */

export type MissionType = "BUG_HEALING" | "MIGRATION";

export const MISSION_STATUSES = [
  "PENDING",
  "PROVISIONING",
  "REPRODUCING",
  "GROUNDING",
  "REASONING",
  "TESTING",
  "REVIEWING",
  "VERIFIED",
  "NOTHING_TO_FIX",
  "FAILED",
  "ABORTED",
] as const;

export type MissionStatus = (typeof MISSION_STATUSES)[number];

/** Statuses after which no further events arrive. */
export const TERMINAL_STATUSES: readonly MissionStatus[] = [
  "VERIFIED",
  "NOTHING_TO_FIX",
  "FAILED",
  "ABORTED",
];

export const MAX_ITERATIONS = 5;

/** Mission ids produced by `POST /api/v1/replays/{id}/play` carry this prefix. */
export const REPLAY_ID_PREFIX = "rp_";

export interface CreateMissionRequest {
  type: MissionType;
  repo_url?: string;
  git_ref?: string;
  test_command?: string;
  swe_instance_id?: string | null;
  hint?: string;
}

export interface CreateMissionResponse {
  id: string;
  status: MissionStatus;
  stream: string;
}

export interface Attempt {
  id: string;
  iteration: number;
  exit_code: number;
  fail_to_pass: number;
  pass_to_pass_broken: number;
  patch_lines: number;
  selected: boolean;
  patch: string;
}

export interface ModelUsage {
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
}

export interface Mission {
  id: string;
  type: MissionType;
  repo_url: string | null;
  git_ref: string | null;
  test_command: string | null;
  swe_instance_id: string | null;
  status: MissionStatus;
  iteration: number;
  spend_usd: number;
  created_at: string;
  attempts: Attempt[];
  usage: ModelUsage[];
}

export interface DiffFile {
  path: string;
  original: string;
  modified: string;
  language: string;
}

export interface ReplaySummary {
  id: string;
  title: string;
  type: MissionType;
  repo_url: string | null;
  swe_instance_id: string | null;
  status: MissionStatus;
  iterations: number;
  resolved: boolean;
  duration_s: number;
}

export interface SweInstance {
  id: string;
  repo: string;
  short_problem: string;
}

export interface Health {
  ok: boolean;
  sandbox_backend: string;
  models: { ultra: string; super: string; nano: string };
}

/* ---------------------------------------------------------------- SSE events */

export interface StatusEventData {
  status: MissionStatus;
  iteration: number;
}

export interface ThoughtEventData {
  stage: string;
  model: string;
  text: string;
}

export interface TavilyEventData {
  query: string;
  results: number;
  ms: number;
}

export type TerminalStream = "stdout" | "stderr" | "cmd";

export interface TerminalEventData {
  attempt: string;
  stream: TerminalStream;
  line: string;
}

export interface TestsEventData {
  attempt: string;
  exit_code: number;
  fail_to_pass: number;
  pass_to_pass_broken: number;
  total: number;
}

export interface PatchFileStat {
  path: string;
  added: number;
  removed: number;
}

export interface PatchEventData {
  attempt: string;
  files: PatchFileStat[];
}

export type ReviewVerdict = "APPROVE" | "REJECT";

export interface ReviewEventData {
  attempt: string;
  verdict: ReviewVerdict;
  reasons: string[];
}

export type UsageEventData = ModelUsage;

export interface ErrorEventData {
  message: string;
}

export interface DoneEventData {
  status: MissionStatus;
  selected_attempt: string | null;
  iterations: number;
  spend_usd: number;
  /** LangSmith trace link when tracing is enabled server-side. */
  trace_url: string | null;
}

export type MissionEvent =
  | { id: number; name: "status"; data: StatusEventData }
  | { id: number; name: "thought"; data: ThoughtEventData }
  | { id: number; name: "tavily"; data: TavilyEventData }
  | { id: number; name: "terminal"; data: TerminalEventData }
  | { id: number; name: "tests"; data: TestsEventData }
  | { id: number; name: "patch"; data: PatchEventData }
  | { id: number; name: "review"; data: ReviewEventData }
  | { id: number; name: "usage"; data: UsageEventData }
  | { id: number; name: "error"; data: ErrorEventData }
  | { id: number; name: "done"; data: DoneEventData };

export type MissionEventName = MissionEvent["name"];

export const MISSION_EVENT_NAMES: readonly MissionEventName[] = [
  "status",
  "thought",
  "tavily",
  "terminal",
  "tests",
  "patch",
  "review",
  "usage",
  "error",
  "done",
];

/** Model tier derived from a Token Factory model id. */
export type ModelTier = "ULTRA" | "SUPER" | "NANO" | "MODEL";

export type ConnectionState =
  | "idle"
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed";
