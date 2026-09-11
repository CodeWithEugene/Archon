import { create } from "zustand";
import { getMissionDiff } from "../lib/api";
import { isTerminalStatus } from "../lib/format";
import type {
  ConnectionState,
  Mission,
  MissionEvent,
  ModelUsage,
} from "../lib/types";
import { EMPTY_MISSION_DATA, applyEventToState, mergeUsage } from "./reducer";
import type { MissionData } from "./types";

export type { DiffState, TerminalLine, TimelineEntry } from "./types";

interface MissionActions {
  /** Clears everything and binds the store to a mission id. */
  attach: (missionId: string) => void;
  /** Folds a `GET /api/v1/missions/{id}` snapshot into the live state. */
  hydrate: (mission: Mission) => void;
  applyEvent: (event: MissionEvent) => void;
  setConnection: (state: ConnectionState) => void;
  setActiveTerminalTab: (attempt: string) => void;
  loadDiff: (missionId: string) => Promise<void>;
}

export type MissionStore = MissionData & MissionActions;

export const useMissionStore = create<MissionStore>()((set, get) => ({
  ...EMPTY_MISSION_DATA,

  attach: (missionId) => set({ ...EMPTY_MISSION_DATA, missionId }),

  setConnection: (connection) => set({ connection }),

  setActiveTerminalTab: (activeTerminalTab) => set({ activeTerminalTab }),

  hydrate: (mission) =>
    set((state) => {
      const selected = mission.attempts.find((a) => a.selected);
      // The stream is authoritative for usage once it starts talking; the REST
      // snapshot only fills the gap before (or instead of) the first frame.
      const usage = state.usageFromStream
        ? {}
        : mission.usage.reduce(
            (acc, entry) => mergeUsage(acc.usageByModel, acc.usageOrder, entry),
            {
              usageByModel: {} as Record<string, ModelUsage>,
              usageOrder: [] as string[],
            },
          );
      return {
        mission,
        // A snapshot must not rewind a status the stream already advanced past.
        status: state.timeline.length > 0 ? state.status : mission.status,
        iteration: Math.max(state.iteration, mission.iteration),
        reportedSpend: Math.max(state.reportedSpend, mission.spend_usd),
        finished: state.finished || isTerminalStatus(mission.status),
        selectedAttempt: selected?.id ?? state.selectedAttempt,
        ...usage,
      };
    }),

  applyEvent: (event) => {
    set((state) => applyEventToState(state, event));

    // The diff endpoint only has something to say once an attempt is selected.
    const approved = event.name === "review" && event.data.verdict === "APPROVE";
    if (event.name === "done" || approved) {
      void get().loadDiff(get().missionId ?? "");
    }
  },

  loadDiff: async (missionId) => {
    if (!missionId) return;
    set({ diffState: "loading", diffError: null });
    try {
      const files = await getMissionDiff(missionId);
      set({ diff: files, diffState: "ready", diffError: null });
    } catch (error) {
      set({
        diffState: "error",
        diffError:
          error instanceof Error ? error.message : "Failed to load the diff",
      });
    }
  },
}));
