"use client";

import { formatUsd, isReplayMission, shortRepo } from "@/lib/format";
import { MAX_ITERATIONS, type ConnectionState, type Mission, type MissionStatus } from "@/lib/types";
import { StatusPill } from "@/components/ui/StatusPill";

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  idle: "idle",
  connecting: "connecting",
  open: "streaming",
  reconnecting: "reconnecting",
  closed: "stream closed",
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-faint">
        {label}
      </span>
      <span className="font-mono text-[12px] text-text">{value}</span>
    </div>
  );
}

export function CockpitHeader({
  missionId,
  mission,
  status,
  iteration,
  spend,
  connection,
}: {
  missionId: string;
  mission: Mission | null;
  status: MissionStatus;
  iteration: number;
  spend: number;
  connection: ConnectionState;
}) {
  const target =
    mission?.swe_instance_id ?? shortRepo(mission?.repo_url ?? null) ?? "—";
  const replay = isReplayMission(missionId);

  return (
    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-5 gap-y-2">
      {replay ? (
        <span className="border border-accent/60 bg-accent/10 px-2 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-accent">
          Replay
        </span>
      ) : null}

      <StatusPill status={status} />

      <div className="flex min-w-0 flex-col">
        <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-faint">
          {mission?.type ?? "MISSION"}
        </span>
        <span className="truncate font-mono text-[12px] text-text" title={target}>
          {target}
        </span>
      </div>

      <Stat label="Iteration" value={`${iteration}/${MAX_ITERATIONS}`} />
      <Stat label="Spend" value={formatUsd(spend)} />
      <Stat label="Mission" value={missionId} />

      <span
        className="ml-auto flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-faint"
        aria-live="polite"
      >
        <span
          aria-hidden
          className={`size-1.5 rounded-full ${
            connection === "open"
              ? "bg-ok archon-live-dot"
              : connection === "reconnecting" || connection === "connecting"
                ? "bg-warn archon-live-dot"
                : "bg-faint"
          }`}
        />
        {CONNECTION_LABEL[connection]}
      </span>
    </div>
  );
}
