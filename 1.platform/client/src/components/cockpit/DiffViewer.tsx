"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { EmptyState, Panel } from "@/components/ui/Panel";
import type {
  DiffFile,
  PatchFileStat,
  ReviewEventData,
  TestsEventData,
} from "@/lib/types";
import type { DiffState } from "@/store/mission";

// Monaco reaches for `window` and `self` during module init.
const MonacoDiff = dynamic(() => import("./MonacoDiff"), { ssr: false });

function Stat({ stats }: { stats: PatchFileStat | undefined }) {
  if (!stats) return null;
  return (
    <span className="shrink-0 font-mono text-[11px]">
      <span className="text-ok">+{stats.added}</span>{" "}
      <span className="text-bad">-{stats.removed}</span>
    </span>
  );
}

function TestsSummary({ tests }: { tests: TestsEventData }) {
  const green = tests.exit_code === 0 && tests.pass_to_pass_broken === 0;
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-sm border px-1.5 py-px font-mono text-[10px] ${
        green
          ? "border-ok/60 bg-ok/10 text-ok"
          : "border-bad/60 bg-bad/10 text-bad"
      }`}
    >
      {green ? "TESTS GREEN" : "TESTS RED"}
      <span aria-hidden className="text-faint">
        |
      </span>
      <span>
        {tests.fail_to_pass} f2p · {tests.pass_to_pass_broken} broken ·{" "}
        {tests.total} total
      </span>
    </span>
  );
}

function VerdictChip({ review }: { review: ReviewEventData }) {
  const approved = review.verdict === "APPROVE";
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-1.5 py-px font-mono text-[10px] tracking-[0.14em] ${
        approved
          ? "border-ok/60 bg-ok/10 text-ok"
          : "border-bad/60 bg-bad/10 text-bad"
      }`}
      title={review.reasons.join(" · ")}
    >
      {review.verdict}
    </span>
  );
}

export function DiffViewer({
  files,
  state,
  error,
  attempt,
  stats,
  tests,
  review,
  onRetry,
  className = "",
}: {
  files: DiffFile[];
  state: DiffState;
  error: string | null;
  attempt: string | null;
  stats: PatchFileStat[];
  tests: TestsEventData | undefined;
  review: ReviewEventData | undefined;
  onRetry: () => void;
  className?: string;
}) {
  // Only the explicit user choice is state; which file is open is derived, so
  // a new diff payload cannot leave a stale path selected.
  const [pickedPath, setPickedPath] = useState<string | null>(null);

  const open = useMemo(
    () =>
      files.find((file) => file.path === pickedPath) ?? files[0] ?? null,
    [files, pickedPath],
  );
  const openPath = open?.path ?? null;

  const statsByPath = useMemo(
    () => new Map(stats.map((entry) => [entry.path, entry])),
    [stats],
  );

  return (
    <Panel
      title="Patch"
      subtitle={attempt ? `attempt ${attempt}` : undefined}
      className={className}
      bodyClassName="flex flex-col overflow-hidden"
      actions={
        tests || review ? (
          <>
            {review ? <VerdictChip review={review} /> : null}
            {tests ? <TestsSummary tests={tests} /> : null}
          </>
        ) : undefined
      }
    >
      {state === "error" ? (
        <EmptyState>
          <span className="flex flex-col items-center gap-3">
            <span className="text-bad">{error ?? "Could not load the diff"}</span>
            <button
              type="button"
              onClick={onRetry}
              className="border border-line-strong px-3 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-muted hover:border-accent/60 hover:text-accent"
            >
              Retry
            </button>
          </span>
        </EmptyState>
      ) : files.length === 0 ? (
        <EmptyState>
          {state === "loading"
            ? "Loading diff…"
            : "No patch selected yet — the diff appears once an attempt is approved."}
        </EmptyState>
      ) : (
        <>
          <ul className="flex shrink-0 flex-col border-b border-line bg-bg">
            {files.map((file) => {
              const active = file.path === openPath;
              return (
                <li key={file.path}>
                  <button
                    type="button"
                    aria-expanded={active}
                    onClick={() => setPickedPath(file.path)}
                    className={`flex w-full items-center gap-3 border-l-2 px-3 py-1.5 text-left transition-colors ${
                      active
                        ? "border-accent bg-panel"
                        : "border-transparent hover:bg-panel-alt"
                    }`}
                  >
                    <span
                      aria-hidden
                      className={`font-mono text-[10px] ${active ? "text-accent" : "text-faint"}`}
                    >
                      {active ? "▾" : "▸"}
                    </span>
                    <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-text">
                      {file.path}
                    </span>
                    <Stat stats={statsByPath.get(file.path)} />
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="min-h-0 flex-1">
            {open ? <MonacoDiff key={open.path} file={open} /> : null}
          </div>
        </>
      )}
    </Panel>
  );
}
