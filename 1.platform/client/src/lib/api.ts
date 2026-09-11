import {
  decodeCreateMission,
  decodeDiffFile,
  decodeHealth,
  decodeMission,
  decodeReplay,
  decodeSweInstance,
} from "./decode";
import { API_BASE, IS_MOCK } from "./env";
import { arr, parseJson, str } from "./parse";
import type {
  CreateMissionRequest,
  CreateMissionResponse,
  DiffFile,
  Health,
  Mission,
  ReplaySummary,
  SweInstance,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  /** True when the request never reached the orchestrator (DNS, CORS, offline). */
  readonly unreachable: boolean;

  constructor(message: string, status: number, unreachable = false) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.unreachable = unreachable;
  }

  get isUnauthorized(): boolean {
    return this.status === 401 || this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

/** The mock module is loaded lazily so it never enters a live production bundle. */
function mock() {
  return import("../mock/server");
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  const text = await response.text().catch(() => "");
  const body = parseJson(text);
  const detail =
    typeof body === "object" && body !== null && "detail" in body
      ? str((body as Record<string, unknown>).detail)
      : "";
  const message =
    detail || text.slice(0, 200) || `${response.status} ${response.statusText}`;
  return new ApiError(message, response.status);
}

async function request(
  path: string,
  init: RequestInit = {},
  token?: string | null,
): Promise<unknown> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      `Cannot reach the orchestrator at ${API_BASE}`,
      0,
      true,
    );
  }

  if (!response.ok) throw await errorFromResponse(response);
  if (response.status === 204) return null;

  const text = await response.text();
  return text.length > 0 ? parseJson(text) : null;
}

/* ------------------------------------------------------------------ queries */

export async function getHealth(): Promise<Health> {
  if (IS_MOCK) return (await mock()).mockHealth();
  return decodeHealth(await request("/healthz"));
}

export async function listSweInstances(): Promise<SweInstance[]> {
  if (IS_MOCK) return (await mock()).mockSweInstances();
  return arr(await request("/api/v1/swe-instances")).map(decodeSweInstance);
}

export async function listReplays(): Promise<ReplaySummary[]> {
  if (IS_MOCK) return (await mock()).mockReplays();
  return arr(await request("/api/v1/replays")).map(decodeReplay);
}

export async function getMission(id: string): Promise<Mission> {
  if (IS_MOCK) return (await mock()).mockMission(id);
  return decodeMission(await request(`/api/v1/missions/${encodeURIComponent(id)}`));
}

export async function getMissionDiff(id: string): Promise<DiffFile[]> {
  if (IS_MOCK) return (await mock()).mockDiff();
  const path = `/api/v1/missions/${encodeURIComponent(id)}/diff`;
  return arr(await request(path)).map(decodeDiffFile);
}

/* ----------------------------------------------------------------- mutations */

export async function createMission(
  body: CreateMissionRequest,
  token: string | null,
): Promise<CreateMissionResponse> {
  if (IS_MOCK) return (await mock()).mockCreateMission();
  const raw = await request(
    "/api/v1/missions",
    { method: "POST", body: JSON.stringify(body) },
    token,
  );
  return decodeCreateMission(raw);
}

export async function playReplay(id: string): Promise<CreateMissionResponse> {
  if (IS_MOCK) return (await mock()).mockPlayReplay(id);
  const raw = await request(
    `/api/v1/replays/${encodeURIComponent(id)}/play`,
    { method: "POST" },
  );
  return decodeCreateMission(raw);
}

export async function abortMission(
  id: string,
  token: string | null,
): Promise<void> {
  if (IS_MOCK) {
    (await mock()).mockAbort();
    return;
  }
  await request(
    `/api/v1/missions/${encodeURIComponent(id)}/abort`,
    { method: "POST" },
    token,
  );
}

/* --------------------------------------------------------------------- urls */

export function patchDownloadUrl(id: string): string {
  return `${API_BASE}/api/v1/missions/${encodeURIComponent(id)}/patch`;
}

export function patchFileName(id: string): string {
  return `archon-${id}.patch`;
}
