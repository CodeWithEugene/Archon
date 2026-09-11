"use client";

import dynamic from "next/dynamic";
import { attemptLabel } from "@/lib/format";
import { EmptyState, Panel } from "@/components/ui/Panel";
import type { TerminalLine } from "@/store/mission";
import type { TestsEventData } from "@/lib/types";

// xterm touches `window` on import, so it must never be server-rendered.
const XtermView = dynamic(() => import("./XtermView"), {
  ssr: false,
  loading: () => (
    <div className="p-3 font-mono text-[11px] text-faint">
      loading terminal…
    </div>
  ),
});

function TestsBadge({ tests }: { tests: TestsEventData }) {
  const green = tests.exit_code === 0 && tests.pass_to_pass_broken === 0;
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-sm border px-1.5 py-px font-mono text-[10px] ${
        green
          ? "border-ok/60 bg-ok/10 text-ok"
          : "border-bad/60 bg-bad/10 text-bad"
      }`}
      title={`exit ${tests.exit_code}`}
    >
      <span>F2P {tests.fail_to_pass}</span>
      <span aria-hidden className="text-faint">
        |
      </span>
      <span>P2P broken {tests.pass_to_pass_broken}</span>
    </span>
  );
}

export function TerminalPanel({
  attempts,
  active,
  onSelect,
  terminals,
  tests,
  className = "",
}: {
  attempts: string[];
  active: string | null;
  onSelect: (attempt: string) => void;
  terminals: Record<string, TerminalLine[]>;
  tests: Record<string, TestsEventData>;
  className?: string;
}) {
  const current = active && attempts.includes(active) ? active : attempts[0];
  const lines = current ? (terminals[current] ?? []) : [];
  const currentTests = current ? tests[current] : undefined;

  return (
    <Panel
      title="Sandbox"
      className={className}
      bodyClassName="flex flex-col overflow-hidden bg-panel"
      actions={currentTests ? <TestsBadge tests={currentTests} /> : undefined}
    >
      {attempts.length === 0 ? (
        <EmptyState>No sandbox output yet.</EmptyState>
      ) : (
        <>
          <div
            role="tablist"
            aria-label="Attempts"
            className="flex shrink-0 gap-px overflow-x-auto border-b border-line bg-bg"
          >
            {attempts.map((attempt) => {
              const selected = attempt === current;
              const result = tests[attempt];
              return (
                <button
                  key={attempt}
                  role="tab"
                  aria-selected={selected}
                  type="button"
                  onClick={() => onSelect(attempt)}
                  className={`flex shrink-0 items-center gap-2 border-b-2 px-3 py-1.5 font-mono text-[11px] transition-colors ${
                    selected
                      ? "border-accent bg-panel text-text"
                      : "border-transparent text-muted hover:bg-panel-alt hover:text-text"
                  }`}
                >
                  {attemptLabel(attempt)}
                  {result ? (
                    <span
                      aria-hidden
                      className={`size-1.5 rounded-full ${
                        result.exit_code === 0 &&
                        result.pass_to_pass_broken === 0
                          ? "bg-ok"
                          : "bg-bad"
                      }`}
                    />
                  ) : null}
                </button>
              );
            })}
          </div>
          <div className="min-h-0 flex-1">
            {current ? <XtermView key={current} lines={lines} /> : null}
          </div>
        </>
      )}
    </Panel>
  );
}
