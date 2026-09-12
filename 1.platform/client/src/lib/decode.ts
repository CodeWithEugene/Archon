import {
  arr,
  asRecord,
  bool,
  missionStatus,
  missionType,
  nullableStr,
  num,
  reviewVerdict,
  str,
  strArray,
  terminalStream,
} from "./parse";
import type {
  Attempt,
  CreateMissionResponse,
  DiffFile,
  Health,
  Mission,
  MissionEvent,
  MissionEventName,
  ModelUsage,
  PatchFileStat,
  ReplaySummary,
  SweInstance,
} from "./types";

export function decodeAttempt(raw: unknown): Attempt {
  const r = asRecord(raw);
  return {
    id: str(r.id, "unknown"),
    iteration: num(r.iteration),
    exit_code: num(r.exit_code, -1),
    fail_to_pass: num(r.fail_to_pass),
    pass_to_pass_broken: num(r.pass_to_pass_broken),
    patch_lines: num(r.patch_lines),
    selected: bool(r.selected),
    patch: str(r.patch),
  };
}

export function decodeUsage(raw: unknown): ModelUsage {
  const r = asRecord(raw);
  return {
    model: str(r.model, "unknown"),
    prompt_tokens: num(r.prompt_tokens),
    completion_tokens: num(r.completion_tokens),
    cost_usd: num(r.cost_usd),
  };
}

export function decodeMission(raw: unknown): Mission {
  const r = asRecord(raw);
  return {
    id: str(r.id),
    type: missionType(r.type),
    repo_url: nullableStr(r.repo_url),
    git_ref: nullableStr(r.git_ref),
    test_command: nullableStr(r.test_command),
    swe_instance_id: nullableStr(r.swe_instance_id),
    status: missionStatus(r.status),
    iteration: num(r.iteration),
    spend_usd: num(r.spend_usd),
    created_at: str(r.created_at),
    attempts: arr(r.attempts).map(decodeAttempt),
    usage: arr(r.usage).map(decodeUsage),
  };
}

export function decodeCreateMission(raw: unknown): CreateMissionResponse {
  const r = asRecord(raw);
  const id = str(r.id);
  return {
    id,
    status: missionStatus(r.status),
    stream: str(r.stream, `/api/v1/missions/${id}/events`),
  };
}

export function decodeDiffFile(raw: unknown): DiffFile {
  const r = asRecord(raw);
  return {
    path: str(r.path, "unknown"),
    original: str(r.original),
    modified: str(r.modified),
    language: str(r.language, "plaintext"),
  };
}

export function decodeReplay(raw: unknown): ReplaySummary {
  const r = asRecord(raw);
  return {
    id: str(r.id),
    title: str(r.title, "Untitled run"),
    type: missionType(r.type),
    repo_url: nullableStr(r.repo_url),
    swe_instance_id: nullableStr(r.swe_instance_id),
    status: missionStatus(r.status, "VERIFIED"),
    iterations: num(r.iterations),
    resolved: bool(r.resolved),
    duration_s: num(r.duration_s),
  };
}

export function decodeSweInstance(raw: unknown): SweInstance {
  const r = asRecord(raw);
  return {
    id: str(r.id),
    repo: str(r.repo),
    short_problem: str(r.short_problem),
  };
}

export function decodeHealth(raw: unknown): Health {
  const r = asRecord(raw);
  const models = asRecord(r.models);
  return {
    ok: bool(r.ok, true),
    sandbox_backend: str(r.sandbox_backend, "unknown"),
    models: {
      ultra: str(models.ultra, "—"),
      super: str(models.super, "—"),
      nano: str(models.nano, "—"),
    },
  };
}

function decodePatchFiles(raw: unknown): PatchFileStat[] {
  return arr(raw).map((item) => {
    const f = asRecord(item);
    return {
      path: str(f.path, "unknown"),
      added: num(f.added),
      removed: num(f.removed),
    };
  });
}

/**
 * Turn a raw SSE frame into a typed event. Returns `null` for unknown event
 * names so that a future server-side addition cannot break an old cockpit.
 */
export function decodeMissionEvent(
  name: string,
  payload: unknown,
  id: number,
): MissionEvent | null {
  const r = asRecord(payload);
  switch (name as MissionEventName) {
    case "status":
      return {
        id,
        name: "status",
        data: { status: missionStatus(r.status), iteration: num(r.iteration) },
      };
    case "thought":
      return {
        id,
        name: "thought",
        data: {
          stage: str(r.stage, "REASONING"),
          model: str(r.model),
          text: str(r.text),
        },
      };
    case "tavily":
      return {
        id,
        name: "tavily",
        data: { query: str(r.query), results: num(r.results), ms: num(r.ms) },
      };
    case "terminal":
      return {
        id,
        name: "terminal",
        data: {
          attempt: str(r.attempt, "baseline"),
          stream: terminalStream(r.stream),
          line: str(r.line),
        },
      };
    case "tests":
      return {
        id,
        name: "tests",
        data: {
          attempt: str(r.attempt, "baseline"),
          exit_code: num(r.exit_code, -1),
          fail_to_pass: num(r.fail_to_pass),
          pass_to_pass_broken: num(r.pass_to_pass_broken),
          total: num(r.total),
        },
      };
    case "patch":
      return {
        id,
        name: "patch",
        data: {
          attempt: str(r.attempt, "baseline"),
          files: decodePatchFiles(r.files),
        },
      };
    case "review":
      return {
        id,
        name: "review",
        data: {
          attempt: str(r.attempt, "baseline"),
          verdict: reviewVerdict(r.verdict),
          reasons: strArray(r.reasons),
        },
      };
    case "usage":
      return { id, name: "usage", data: decodeUsage(r) };
    case "error":
      return {
        id,
        name: "error",
        data: { message: str(r.message, "Unknown orchestrator error") },
      };
    case "done":
      return {
        id,
        name: "done",
        data: {
          status: missionStatus(r.status, "FAILED"),
          selected_attempt: nullableStr(r.selected_attempt),
          iterations: num(r.iterations),
          spend_usd: num(r.spend_usd),
          trace_url: nullableStr(r.trace_url),
        },
      };
    default:
      return null;
  }
}
