"use client";

import type { ReactNode } from "react";

export function Field({
  label,
  htmlFor,
  hint,
  optional,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: ReactNode;
  optional?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={htmlFor}
        className="flex items-baseline gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted"
      >
        {label}
        {optional ? <span className="text-faint">optional</span> : null}
      </label>
      {children}
      {hint ? (
        <p className="text-[12px] leading-relaxed text-faint">{hint}</p>
      ) : null}
    </div>
  );
}

export function Segmented({
  name,
  value,
  onChange,
  options,
}: {
  name: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div
      role="radiogroup"
      aria-label={name}
      className="inline-flex w-full border border-line-strong"
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={`flex-1 px-3 py-2 font-mono text-[12px] uppercase tracking-[0.12em] transition-colors ${
              active
                ? "bg-accent/15 text-accent"
                : "text-muted hover:bg-panel-alt hover:text-text"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function SubmitButton({
  pending,
  children,
}: {
  pending: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex items-center justify-center gap-2 border border-accent bg-accent/15 px-4 py-2.5 font-mono text-[12px] font-semibold uppercase tracking-[0.18em] text-accent transition-colors hover:bg-accent/25 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {pending ? (
        <span aria-hidden className="size-1.5 rounded-full bg-current archon-live-dot" />
      ) : null}
      {pending ? "Starting…" : children}
    </button>
  );
}
