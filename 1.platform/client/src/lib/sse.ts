import { decodeMissionEvent } from "./decode";
import { API_BASE, IS_MOCK } from "./env";
import { parseJson } from "./parse";
import {
  MISSION_EVENT_NAMES,
  type ConnectionState,
  type MissionEvent,
} from "./types";

export interface MissionStreamHandlers {
  onEvent: (event: MissionEvent) => void;
  onStateChange?: (state: ConnectionState) => void;
}

export interface MissionStreamHandle {
  close: () => void;
}

/**
 * Subscribes to `GET /api/v1/missions/{id}/events`.
 *
 * `EventSource` replays from `Last-Event-ID` on its own reconnect, so the only
 * bookkeeping here is closing the socket once a terminal `done` frame lands —
 * otherwise the browser would reconnect to a finished mission forever.
 */
export function openMissionStream(
  missionId: string,
  handlers: MissionStreamHandlers,
): MissionStreamHandle {
  if (IS_MOCK) return openMockStream(missionId, handlers);

  const url = `${API_BASE}/api/v1/missions/${encodeURIComponent(missionId)}/events`;
  const source = new EventSource(url);
  let closed = false;
  let everOpen = false;

  const setState = (state: ConnectionState) => handlers.onStateChange?.(state);
  setState("connecting");

  const close = () => {
    if (closed) return;
    closed = true;
    source.close();
    setState("closed");
  };

  source.onopen = () => {
    everOpen = true;
    setState("open");
  };

  source.onerror = () => {
    // readyState CLOSED means the browser gave up; CONNECTING means it retries.
    if (source.readyState === EventSource.CLOSED) close();
    else setState(everOpen ? "reconnecting" : "connecting");
  };

  for (const name of MISSION_EVENT_NAMES) {
    source.addEventListener(name, (raw: MessageEvent<string>) => {
      if (closed) return;
      const id = Number.parseInt(raw.lastEventId, 10);
      const event = decodeMissionEvent(
        name,
        parseJson(raw.data),
        Number.isFinite(id) ? id : 0,
      );
      if (!event) return;
      handlers.onEvent(event);
      if (event.name === "done") close();
    });
  }

  return { close };
}

function openMockStream(
  missionId: string,
  handlers: MissionStreamHandlers,
): MissionStreamHandle {
  let cancel: (() => void) | null = null;
  let closed = false;

  void import("../mock/server").then((mod) => {
    if (closed) return;
    cancel = mod.mockOpenStream(missionId, handlers).close;
  });

  return {
    close: () => {
      closed = true;
      cancel?.();
    },
  };
}
