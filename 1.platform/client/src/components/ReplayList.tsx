"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, listReplays, playReplay } from "@/lib/api";
import { formatDuration, shortRepo } from "@/lib/format";
import type { ReplaySummary } from "@/lib/types";
import { UnreachableState } from "./ui/ErrorState";

export function ReplayList() {
  const router = useRouter();
  const [replays, setReplays] = useState<ReplaySummary[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [playing, setPlaying] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const rows = await listReplays();
        if (cancelled) return;
        setReplays(rows);
        setError(null);
      } catch (cause) {
        if (cancelled) return;
        setError(
          cause instanceof ApiError
            ? cause
            : new ApiError("Failed to list recorded runs", 0, true),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  function retry() {
    setLoading(true);
    setError(null);
    setAttempt((n) => n + 1);
  }

  async function play(replay: ReplaySummary) {
    setPlaying(replay.id);
    try {
      const created = await playReplay(replay.id);
      router.push(`/missions/${created.id}`);
    } catch {
      setPlaying(null);
      setError(new ApiError("Could not start the replay", 0, true));
    }
  }

  if (error && !replays) {
    return (
      <UnreachableState
        onRetry={retry}
        retrying={loading}
        detail={error.message}
      />
    );
  }

  if (loading && !replays) {
    return (
      <p className="border border-line bg-panel px-4 py-6 text-[13px] text-faint">
        Loading recorded runs…
      </p>
    );
  }

  if (!replays || replays.length === 0) {
    return (
      <p className="border border-line bg-panel px-4 py-6 text-[13px] text-faint">
        No recordings on this server yet.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-line border border-line bg-panel">
      {replays.map((replay) => (
        <li
          key={replay.id}
          className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 transition-colors hover:bg-panel-alt"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span
                aria-hidden
                className={`size-1.5 rounded-full ${replay.resolved ? "bg-ok" : "bg-bad"}`}
              />
              <p className="truncate text-[13px] font-medium text-text">
                {replay.title}
              </p>
            </div>
            <p className="mt-1 truncate font-mono text-[11px] text-faint">
              {replay.swe_instance_id ?? shortRepo(replay.repo_url) ?? "—"}
            </p>
          </div>

          <dl className="flex shrink-0 items-center gap-4 font-mono text-[11px] text-muted">
            <div className="flex flex-col">
              <dt className="text-[9px] uppercase tracking-[0.16em] text-faint">
                Type
              </dt>
              <dd>{replay.type === "MIGRATION" ? "MIGR" : "BUG"}</dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-[9px] uppercase tracking-[0.16em] text-faint">
                Iters
              </dt>
              <dd>{replay.iterations}</dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-[9px] uppercase tracking-[0.16em] text-faint">
                Time
              </dt>
              <dd>{formatDuration(replay.duration_s)}</dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-[9px] uppercase tracking-[0.16em] text-faint">
                Result
              </dt>
              <dd className={replay.resolved ? "text-ok" : "text-bad"}>
                {replay.resolved ? "RESOLVED" : "UNRESOLVED"}
              </dd>
            </div>
          </dl>

          <button
            type="button"
            onClick={() => void play(replay)}
            disabled={playing !== null}
            className="shrink-0 border border-accent/60 bg-accent/10 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
          >
            {playing === replay.id ? "Starting…" : "Play"}
          </button>
        </li>
      ))}
    </ul>
  );
}
