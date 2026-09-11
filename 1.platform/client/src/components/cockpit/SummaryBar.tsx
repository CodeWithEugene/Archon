"use client";

import { useState } from "react";
import { abortMission, patchDownloadUrl, patchFileName } from "@/lib/api";
import { formatTokens, formatUsd, shortModelName } from "@/lib/format";
import { readDemoToken } from "@/lib/token";
import { ModelBadge } from "@/components/ui/ModelBadge";
import type { ModelUsage } from "@/lib/types";

function CopySnippet({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      onClick={() => {
        // `navigator.clipboard` is undefined on insecure origins.
        if (!navigator.clipboard) return;
        void navigator.clipboard
          .writeText(text)
          .then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1600);
          })
          .catch(() => setCopied(false));
      }}
      title="Copy to clipboard"
      className="group flex min-w-0 items-center gap-2 border border-line-strong bg-bg px-2.5 py-1.5 font-mono text-[11px] text-muted transition-colors hover:border-accent/60 hover:text-text"
    >
      <span className="truncate">{text}</span>
      <span
        className={`shrink-0 text-[10px] uppercase tracking-[0.14em] ${copied ? "text-ok" : "text-faint group-hover:text-accent"}`}
      >
        {copied ? "copied" : "copy"}
      </span>
    </button>
  );
}

export function SummaryBar({
  missionId,
  usage,
  spend,
  running,
  hasPatch,
}: {
  missionId: string;
  usage: ModelUsage[];
  spend: number;
  running: boolean;
  hasPatch: boolean;
}) {
  const [aborting, setAborting] = useState(false);
  const [abortError, setAbortError] = useState<string | null>(null);

  async function abort() {
    setAborting(true);
    setAbortError(null);
    try {
      await abortMission(missionId, readDemoToken());
    } catch (cause) {
      setAbortError(
        cause instanceof Error ? cause.message : "Abort request failed",
      );
    } finally {
      setAborting(false);
    }
  }

  const totalTokens = usage.reduce(
    (acc, entry) => acc + entry.prompt_tokens + entry.completion_tokens,
    0,
  );

  return (
    <footer className="shrink-0 border-t border-line bg-panel-alt">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 px-4 py-2.5">
        <dl className="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-2">
          {usage.length === 0 ? (
            <span className="font-mono text-[11px] text-faint">
              no model calls yet
            </span>
          ) : null}
          {usage.map((entry) => (
            <div key={entry.model} className="flex items-center gap-2">
              <ModelBadge model={entry.model} />
              <div className="flex flex-col">
                <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
                  {shortModelName(entry.model)}
                </dt>
                <dd className="font-mono text-[11px] text-muted">
                  {formatTokens(entry.prompt_tokens)} in ·{" "}
                  {formatTokens(entry.completion_tokens)} out ·{" "}
                  <span className="text-text">{formatUsd(entry.cost_usd)}</span>
                </dd>
              </div>
            </div>
          ))}
          <div className="flex flex-col border-l border-line pl-5">
            <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
              Total
            </dt>
            <dd className="font-mono text-[11px] text-text">
              {formatTokens(totalTokens)} tok · {formatUsd(spend)}
            </dd>
          </div>
        </dl>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {abortError ? (
            <span role="alert" className="font-mono text-[11px] text-bad">
              {abortError}
            </span>
          ) : null}

          <CopySnippet text={`git apply ${patchFileName(missionId)}`} />

          <a
            href={patchDownloadUrl(missionId)}
            download={patchFileName(missionId)}
            aria-disabled={!hasPatch}
            className={`border px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors ${
              hasPatch
                ? "border-accent/60 bg-accent/10 text-accent hover:bg-accent/20"
                : "pointer-events-none border-line-strong text-faint opacity-50"
            }`}
          >
            Download patch
          </a>

          {running ? (
            <button
              type="button"
              onClick={() => void abort()}
              disabled={aborting}
              className="border border-bad/60 bg-bad/10 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-bad transition-colors hover:bg-bad/20 disabled:opacity-50"
            >
              {aborting ? "Aborting…" : "Abort"}
            </button>
          ) : null}
        </div>
      </div>
    </footer>
  );
}
