"use client";

import { DiffEditor, loader, type Monaco } from "@monaco-editor/react";
import * as monaco from "monaco-editor";
import type { DiffFile } from "@/lib/types";

// `@monaco-editor/react` fetches Monaco from a CDN by default. Point it at the
// bundled copy instead so the diff pane still works on a venue network that
// blocks jsdelivr.
declare global {
  interface Window {
    MonacoEnvironment?: monaco.Environment;
  }
}

if (typeof window !== "undefined") {
  window.MonacoEnvironment = {
    getWorker: () =>
      new Worker(
        new URL(
          "monaco-editor/esm/vs/editor/editor.worker.js",
          import.meta.url,
        ),
        { type: "module" },
      ),
  };
  loader.config({ monaco });
}

const THEME = "archon-dark";

function defineTheme(instance: Monaco): void {
  instance.editor.defineTheme(THEME, {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#0e1319",
      "editorGutter.background": "#0e1319",
      "editor.lineHighlightBackground": "#131a22",
      "editorLineNumber.foreground": "#3d4a57",
      "editorLineNumber.activeForeground": "#8a9aab",
      "diffEditor.insertedTextBackground": "#35c46b22",
      "diffEditor.removedTextBackground": "#ff5f5622",
      "diffEditor.insertedLineBackground": "#35c46b16",
      "diffEditor.removedLineBackground": "#ff5f5616",
      "editorOverviewRuler.border": "#1e2831",
      "scrollbarSlider.background": "#2c3945aa",
    },
  });
}

export default function MonacoDiff({ file }: { file: DiffFile }) {
  return (
    <DiffEditor
      height="100%"
      language={file.language || "plaintext"}
      original={file.original}
      modified={file.modified}
      theme={THEME}
      beforeMount={defineTheme}
      loading={
        <span className="font-mono text-[11px] text-faint">
          loading diff editor…
        </span>
      }
      options={{
        renderSideBySide: false,
        readOnly: true,
        originalEditable: false,
        automaticLayout: true,
        fontSize: 12,
        lineHeight: 18,
        fontFamily:
          "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, monospace",
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        renderOverviewRuler: false,
        scrollbar: { alwaysConsumeMouseWheel: false },
      }}
    />
  );
}
