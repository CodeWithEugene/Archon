import { AppHeader } from "@/components/AppHeader";
import { HealthStrip } from "@/components/HealthStrip";
import { MissionForm } from "@/components/MissionForm";
import { ReplayList } from "@/components/ReplayList";

export default function LaunchPage() {
  return (
    <>
      <AppHeader>
        <HealthStrip />
      </AppHeader>

      <main className="archon-grid flex-1">
        <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 lg:py-14">
          <div className="max-w-2xl">
            <h1 className="text-2xl font-semibold tracking-tight text-text sm:text-3xl">
              Hand it a broken repository. Watch it reason, test, and patch.
            </h1>
            <p className="mt-3 text-[14px] leading-relaxed text-muted">
              ARCHON reproduces the failure inside a Nebius sandbox, grounds
              itself against the web, then iterates on candidate patches until
              the suite is green and a reviewer signs off. Every step streams
              here live.
            </p>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
            <section
              aria-labelledby="new-mission"
              className="border border-line bg-panel p-5 sm:p-6"
            >
              <h2
                id="new-mission"
                className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-muted"
              >
                New mission
              </h2>
              <div className="mt-5">
                <MissionForm />
              </div>
            </section>

            <aside className="border border-line-strong bg-panel-alt p-5">
              <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-accent">
                Replay is free
              </h2>
              <p className="mt-3 text-[13px] leading-relaxed text-muted">
                Recorded runs stream from the orchestrator&rsquo;s golden
                dataset and need no credentials — start with one of those.
              </p>
              <p className="mt-3 text-[13px] leading-relaxed text-muted">
                Live mode burns real inference and sandbox time, so it requires
                a demo token. Set it with the control in the header; it stays in
                this browser.
              </p>
              <p className="mt-4 border-t border-line pt-3 font-mono text-[11px] leading-relaxed text-faint">
                Missions are capped at 5 iterations and a per-mission spend
                ceiling. Output is a downloadable patch — ARCHON never pushes.
              </p>
            </aside>
          </div>

          <section aria-labelledby="recorded-runs" className="mt-10">
            <div className="mb-3 flex items-baseline justify-between gap-4">
              <h2
                id="recorded-runs"
                className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-muted"
              >
                Recorded runs
              </h2>
              <span className="font-mono text-[11px] text-faint">
                no token required
              </span>
            </div>
            <ReplayList />
          </section>
        </div>
      </main>
    </>
  );
}
