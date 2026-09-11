"use client";

import { useEffect, useRef } from "react";
import { ModelBadge, ModelName } from "@/components/ui/ModelBadge";
import { EmptyState, Panel } from "@/components/ui/Panel";
import type { TimelineEntry } from "@/store/mission";

function Row({ entry }: { entry: TimelineEntry }) {
  switch (entry.kind) {
    case "status":
      return (
        <li className="flex items-center gap-3 px-3 py-2">
          <span className="h-px flex-1 bg-line" aria-hidden />
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            {entry.data.status.replace(/_/g, " ")}
            <span className="ml-2 text-faint">iter {entry.data.iteration}</span>
          </span>
          <span className="h-px flex-1 bg-line" aria-hidden />
        </li>
      );

    case "thought":
      return (
        <li className="border-l-2 border-line-strong px-3 py-2.5 hover:border-accent/50">
          <div className="flex flex-wrap items-center gap-2">
            <ModelBadge model={entry.data.model} />
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
              {entry.data.stage}
            </span>
            <ModelName model={entry.data.model} />
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-text">
            {entry.data.text}
          </p>
        </li>
      );

    case "tavily":
      return (
        <li className="border-l-2 border-nano/40 px-3 py-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-sm border border-nano/60 bg-nano/10 px-1.5 py-px font-mono text-[10px] tracking-[0.16em] text-nano">
              TAVILY
            </span>
            <span className="font-mono text-[10px] text-faint">
              {entry.data.results} results · {entry.data.ms}ms
            </span>
          </div>
          <p className="mt-1.5 font-mono text-[12px] leading-relaxed text-muted">
            {entry.data.query}
          </p>
        </li>
      );

    case "review": {
      const approved = entry.data.verdict === "APPROVE";
      return (
        <li
          className={`border-l-2 px-3 py-2.5 ${approved ? "border-ok/70" : "border-bad/70"}`}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-sm border px-1.5 py-px font-mono text-[10px] tracking-[0.16em] ${
                approved
                  ? "border-ok/60 bg-ok/10 text-ok"
                  : "border-bad/60 bg-bad/10 text-bad"
              }`}
            >
              {entry.data.verdict}
            </span>
            <span className="font-mono text-[11px] text-muted">
              {entry.data.attempt}
            </span>
          </div>
          <ul className="mt-1.5 space-y-1">
            {entry.data.reasons.map((reason) => (
              <li
                key={reason}
                className="text-[12px] leading-relaxed text-muted before:mr-2 before:text-faint before:content-['—']"
              >
                {reason}
              </li>
            ))}
          </ul>
        </li>
      );
    }

    case "error":
      return (
        <li className="border-l-2 border-bad px-3 py-2.5">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-bad">
            Error
          </span>
          <p className="mt-1.5 text-[13px] leading-relaxed text-bad">
            {entry.data.message}
          </p>
        </li>
      );
  }
}

export function ReasoningStream({
  entries,
  className = "",
}: {
  entries: TimelineEntry[];
  className?: string;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node || !pinnedRef.current) return;
    node.scrollTop = node.scrollHeight;
  }, [entries]);

  return (
    <Panel
      title="Reasoning"
      subtitle={entries.length > 0 ? `${entries.length} events` : undefined}
      className={className}
      bodyClassName="overflow-hidden"
    >
      <div
        ref={scrollRef}
        onScroll={(event) => {
          const el = event.currentTarget;
          pinnedRef.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 48;
        }}
        className="h-full overflow-y-auto"
        aria-live="polite"
        aria-atomic="false"
      >
        {entries.length === 0 ? (
          <EmptyState>Waiting for the first event…</EmptyState>
        ) : (
          <ul className="divide-y divide-line/60 py-1">
            {entries.map((entry) => (
              <Row key={entry.key} entry={entry} />
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
}
