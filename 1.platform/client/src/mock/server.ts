/**
 * In-browser fake orchestrator. Enabled by `NEXT_PUBLIC_ARCHON_MOCK=1`, which
 * makes `src/lib/api.ts` and `src/lib/sse.ts` route here instead of the network,
 * so the cockpit can be developed and screenshotted with no server running.
 */

import type { MissionStreamHandle, MissionStreamHandlers } from "../lib/sse";
import type {
  CreateMissionResponse,
  DiffFile,
  Health,
  Mission,
  MissionEvent,
  ReplaySummary,
  SweInstance,
} from "../lib/types";
import { MOCK_FRAMES, type MockFrame } from "./events";
import {
  MOCK_MISSION_ID,
  mockDiffPayload,
  mockHealthPayload,
  mockMissionFinal,
  mockMissionInitial,
  mockReplaysPayload,
  mockSweInstancesPayload,
} from "./fixtures";

const FRAME_INTERVAL_MS = 150;
const LATENCY_MS = 120;

/** Progress of the single canned run, shared by the stream and the REST fakes. */
const runState = {
  approved: false,
  done: false,
  aborted: false,
};

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), LATENCY_MS));
}

/* ------------------------------------------------------------- REST doubles */

export function mockHealth(): Promise<Health> {
  return delay(mockHealthPayload);
}

export function mockSweInstances(): Promise<SweInstance[]> {
  return delay(mockSweInstancesPayload);
}

export function mockReplays(): Promise<ReplaySummary[]> {
  return delay(mockReplaysPayload);
}

export function mockMission(id: string): Promise<Mission> {
  const mission = runState.done ? mockMissionFinal(id) : mockMissionInitial(id);
  if (runState.aborted) mission.status = "ABORTED";
  return delay(mission);
}

export function mockDiff(): Promise<DiffFile[]> {
  return delay(runState.approved ? mockDiffPayload : []);
}

export function mockCreateMission(): Promise<CreateMissionResponse> {
  resetRun();
  return delay({
    id: MOCK_MISSION_ID,
    status: "PENDING" as const,
    stream: `/api/v1/missions/${MOCK_MISSION_ID}/events`,
  });
}

export function mockPlayReplay(replayId: string): Promise<CreateMissionResponse> {
  resetRun();
  const id = `rp_${replayId.replace(/[^a-z0-9]+/gi, "").slice(0, 10)}`;
  return delay({
    id,
    status: "PENDING" as const,
    stream: `/api/v1/missions/${id}/events`,
  });
}

export function mockAbort(): void {
  runState.aborted = true;
}

function resetRun(): void {
  runState.approved = false;
  runState.done = false;
  runState.aborted = false;
}

/* ----------------------------------------------------------- stream double */

/** Frames carry their id by position, matching the server's monotonic counter. */
function withId(frame: MockFrame, id: number): MissionEvent {
  // The spread of a discriminated union loses its narrowing; the shape is
  // guaranteed by MockFrame being MissionEvent minus `id`.
  return { ...frame, id } as MissionEvent;
}

export function mockOpenStream(
  _missionId: string,
  handlers: MissionStreamHandlers,
): MissionStreamHandle {
  let index = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const close = () => {
    if (closed) return;
    closed = true;
    if (timer !== null) clearTimeout(timer);
    handlers.onStateChange?.("closed");
  };

  const step = () => {
    if (closed) return;

    if (runState.aborted) {
      handlers.onEvent(
        withId(
          {
            name: "done",
            data: {
              status: "ABORTED",
              selected_attempt: null,
              iterations: 2,
              spend_usd: 0.412,
            },
          },
          index + 1,
        ),
      );
      runState.done = true;
      close();
      return;
    }

    const frame = MOCK_FRAMES[index];
    if (!frame) {
      close();
      return;
    }

    index += 1;
    if (frame.name === "review" && frame.data.verdict === "APPROVE") {
      runState.approved = true;
    }
    if (frame.name === "done") runState.done = true;

    handlers.onEvent(withId(frame, index));

    if (frame.name === "done") {
      close();
      return;
    }
    timer = setTimeout(step, FRAME_INTERVAL_MS);
  };

  handlers.onStateChange?.("connecting");
  timer = setTimeout(() => {
    handlers.onStateChange?.("open");
    step();
  }, LATENCY_MS * 2);

  return { close };
}
