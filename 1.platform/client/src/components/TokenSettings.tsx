"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { API_BASE, IS_MOCK } from "@/lib/env";
import { readDemoToken, writeDemoToken } from "@/lib/token";

const TOKEN_EVENT = "archon:token-changed";

function subscribeToToken(onChange: () => void): () => void {
  window.addEventListener(TOKEN_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(TOKEN_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** Header popover for the live-mode bearer token (localStorage `archon.demoToken`). */
export function TokenSettings() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [saved, setSaved] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // localStorage is an external store; reading it through this hook keeps the
  // server render ("no token") and the client render consistent.
  const hasToken = useSyncExternalStore(
    subscribeToToken,
    () => readDemoToken() !== null,
    () => false,
  );

  const toggle = useCallback(() => {
    setOpen((wasOpen) => {
      if (!wasOpen) {
        setValue(readDemoToken() ?? "");
        setSaved(false);
      }
      return !wasOpen;
    });
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const onClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  const save = () => {
    writeDemoToken(value);
    setSaved(true);
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="flex items-center gap-2 border border-line-strong bg-panel px-2.5 py-1.5 font-mono text-[11px] text-muted transition-colors hover:border-accent/60 hover:text-text"
      >
        <span
          aria-hidden
          className={`size-1.5 rounded-full ${hasToken ? "bg-ok" : "bg-faint"}`}
        />
        {hasToken ? "TOKEN SET" : "NO TOKEN"}
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label="Demo token settings"
          className="absolute right-0 top-[calc(100%+8px)] z-50 w-[min(22rem,calc(100vw-2rem))] border border-line-strong bg-panel p-4 shadow-[0_18px_40px_-12px_rgba(0,0,0,0.8)]"
        >
          <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
            Live mode token
          </h3>
          <p className="mt-2 text-[12px] leading-relaxed text-faint">
            Sent as{" "}
            <code className="font-mono text-muted">
              Authorization: Bearer …
            </code>{" "}
            on mission start and abort. Stored in this browser only. Replays
            never need it.
          </p>

          <label
            htmlFor="archon-demo-token"
            className="mt-3 block font-mono text-[10px] uppercase tracking-[0.16em] text-faint"
          >
            ARCHON_DEMO_TOKEN
          </label>
          <input
            id="archon-demo-token"
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
              setSaved(false);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") save();
            }}
            placeholder="paste token"
            className="mt-1 w-full border border-line-strong bg-bg px-2 py-1.5 font-mono text-[12px] text-text placeholder:text-faint"
          />

          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={save}
              className="border border-accent/60 bg-accent/10 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-accent transition-colors hover:bg-accent/20"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => {
                writeDemoToken("");
                setValue("");
                setSaved(false);
              }}
              className="border border-line-strong px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-muted transition-colors hover:text-text"
            >
              Clear
            </button>
            {saved ? (
              <span className="font-mono text-[11px] text-ok">saved</span>
            ) : null}
          </div>

          <dl className="mt-4 space-y-1 border-t border-line pt-3 font-mono text-[10px] text-faint">
            <div className="flex justify-between gap-3">
              <dt>API</dt>
              <dd className="truncate text-muted">{API_BASE}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>MODE</dt>
              <dd className="text-muted">{IS_MOCK ? "mock" : "network"}</dd>
            </div>
          </dl>
        </div>
      ) : null}
    </div>
  );
}
