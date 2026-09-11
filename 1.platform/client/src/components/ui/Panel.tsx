import type { ReactNode } from "react";

export function Panel({
  title,
  subtitle,
  actions,
  children,
  bodyClassName = "",
  className = "",
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  bodyClassName?: string;
  className?: string;
}) {
  return (
    <section
      className={`flex min-h-0 flex-col border border-line bg-panel ${className}`}
      aria-label={title}
    >
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line bg-panel-alt px-3 py-2">
        <div className="flex min-w-0 items-baseline gap-3">
          <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
            {title}
          </h2>
          {subtitle ? (
            <span className="truncate text-[11px] text-faint">{subtitle}</span>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        ) : null}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center p-6 text-center text-[13px] text-faint">
      {children}
    </div>
  );
}
