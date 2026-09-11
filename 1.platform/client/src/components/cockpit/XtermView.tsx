"use client";

import { useEffect, useRef } from "react";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import type { TerminalLine } from "@/store/mission";

const ESC = "\u001b";
const RESET = `${ESC}[0m`;
const ACCENT = `${ESC}[38;2;255;157;46m`;
const RED = `${ESC}[38;2;255;95;86m`;

function render(entry: TerminalLine): string {
  if (entry.stream === "cmd") return `${ACCENT}$ ${entry.line}${RESET}`;
  if (entry.stream === "stderr") return `${RED}${entry.line}${RESET}`;
  return entry.line;
}

/**
 * Thin xterm.js wrapper. The caller keys this by attempt id, so the component
 * only ever has to append: the write cursor is the number of lines already
 * flushed into the emulator.
 */
export default function XtermView({ lines }: { lines: TerminalLine[] }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const writtenRef = useRef(0);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const term = new Terminal({
      convertEol: true,
      cursorBlink: false,
      disableStdin: true,
      fontFamily:
        "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, monospace",
      fontSize: 12,
      lineHeight: 1.35,
      scrollback: 5000,
      theme: {
        background: "#0e1319",
        foreground: "#c9d6e2",
        cursor: "#0e1319",
        selectionBackground: "#2c3945",
      },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(host);

    const doFit = () => {
      try {
        fit.fit();
      } catch {
        /* host is not laid out yet */
      }
    };
    doFit();

    const observer = new ResizeObserver(doFit);
    observer.observe(host);

    termRef.current = term;
    writtenRef.current = 0;

    return () => {
      observer.disconnect();
      term.dispose();
      termRef.current = null;
    };
  }, []);

  useEffect(() => {
    const term = termRef.current;
    if (!term) return;

    if (lines.length < writtenRef.current) {
      term.reset();
      writtenRef.current = 0;
    }
    for (let i = writtenRef.current; i < lines.length; i += 1) {
      term.writeln(render(lines[i]));
    }
    if (lines.length > writtenRef.current) {
      writtenRef.current = lines.length;
      term.scrollToBottom();
    }
  }, [lines]);

  return <div ref={hostRef} className="h-full w-full px-2 py-1" />;
}
