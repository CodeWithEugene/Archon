"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import { API_BASE } from "@/lib/env";
import { shortModelName } from "@/lib/format";
import type { Health } from "@/lib/types";

export function HealthStrip() {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((value) => !cancelled && setHealth(value))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return (
      <span className="flex items-center gap-2 font-mono text-[11px] text-bad">
        <span aria-hidden className="size-1.5 rounded-full bg-bad" />
        offline · {API_BASE}
      </span>
    );
  }

  if (!health) {
    return (
      <span className="font-mono text-[11px] text-faint">checking server…</span>
    );
  }

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-muted">
      <span className="flex items-center gap-2">
        <span
          aria-hidden
          className={`size-1.5 rounded-full ${health.ok ? "bg-ok" : "bg-bad"}`}
        />
        {health.ok ? "online" : "degraded"}
      </span>
      <span className="text-faint">sandbox {health.sandbox_backend}</span>
      <span className="truncate text-faint">
        {shortModelName(health.models.ultra)} ·{" "}
        {shortModelName(health.models.super)} ·{" "}
        {shortModelName(health.models.nano)}
      </span>
    </div>
  );
}
