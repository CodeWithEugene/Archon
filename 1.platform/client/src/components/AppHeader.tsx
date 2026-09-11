"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { IS_MOCK } from "@/lib/env";
import { TokenSettings } from "./TokenSettings";

export function Wordmark() {
  return (
    <Link href="/" className="group flex items-baseline gap-2.5">
      <span
        aria-hidden
        className="inline-block size-2.5 rotate-45 border border-accent bg-accent/25 transition-colors group-hover:bg-accent/60"
      />
      <span className="font-mono text-[15px] font-semibold tracking-[0.32em] text-text">
        ARCHON
      </span>
    </Link>
  );
}

export function AppHeader({ children }: { children?: ReactNode }) {
  return (
    <header className="sticky top-0 z-40 shrink-0 border-b border-line bg-bg/95 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
        <Wordmark />
        <span
          aria-hidden
          className="hidden h-4 w-px bg-line-strong sm:inline-block"
        />
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-2">
          {children}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {IS_MOCK ? (
            <span className="border border-warn/50 bg-warn/10 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-warn">
              Mock data
            </span>
          ) : null}
          <TokenSettings />
        </div>
      </div>
    </header>
  );
}
