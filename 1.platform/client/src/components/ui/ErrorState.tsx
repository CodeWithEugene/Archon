"use client";

import Link from "next/link";
import { API_BASE, IS_MOCK } from "@/lib/env";

export function UnreachableState({
  onRetry,
  retrying,
  detail,
}: {
  onRetry: () => void;
  retrying?: boolean;
  detail?: string | null;
}) {
  return (
    <div className="border border-bad/40 bg-bad/5 p-5">
      <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-bad">
        Orchestrator unreachable
      </h3>
      <p className="mt-2 text-[13px] leading-relaxed text-muted">
        Nothing answered at{" "}
        <code className="font-mono text-text">{API_BASE}</code>. Start the
        FastAPI server, set{" "}
        <code className="font-mono text-text">NEXT_PUBLIC_ARCHON_API</code>, or
        run the cockpit with{" "}
        <code className="font-mono text-text">NEXT_PUBLIC_ARCHON_MOCK=1</code>
        {IS_MOCK ? " (already on)" : ""}.
      </p>
      {detail ? (
        <p className="mt-2 font-mono text-[11px] text-faint">{detail}</p>
      ) : null}
      <button
        type="button"
        onClick={onRetry}
        disabled={retrying}
        className="mt-4 border border-line-strong px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-muted transition-colors hover:border-accent/60 hover:text-accent disabled:opacity-50"
      >
        {retrying ? "Retrying…" : "Retry"}
      </button>
    </div>
  );
}

export function NotFoundState({ missionId }: { missionId: string }) {
  return (
    <div className="border border-line bg-panel p-5">
      <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-warn">
        Mission not found
      </h3>
      <p className="mt-2 text-[13px] leading-relaxed text-muted">
        <code className="font-mono text-text">{missionId}</code> is not in the
        orchestrator&rsquo;s database. It may have been started against a
        different server, or the SQLite file was reset.
      </p>
      <Link
        href="/"
        className="mt-4 inline-block border border-line-strong px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-muted transition-colors hover:border-accent/60 hover:text-accent"
      >
        Back to launch
      </Link>
    </div>
  );
}
