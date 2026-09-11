"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, getMission } from "@/lib/api";
import { isTerminalStatus } from "@/lib/format";
import { openMissionStream } from "@/lib/sse";
import { useMissionStore } from "@/store/mission";
import { AppHeader } from "@/components/AppHeader";
import { NotFoundState, UnreachableState } from "@/components/ui/ErrorState";
import { CockpitHeader } from "./CockpitHeader";
import { DiffViewer } from "./DiffViewer";
import { ReasoningStream } from "./ReasoningStream";
import { SummaryBar } from "./SummaryBar";
import { TerminalPanel } from "./TerminalPanel";

type LoadState = "loading" | "ready" | "notfound" | "unreachable";

export function Cockpit({ missionId }: { missionId: string }) {
  const [load, setLoad] = useState<LoadState>("loading");
  const [loadDetail, setLoadDetail] = useState<string | null>(null);

  const attach = useMissionStore((s) => s.attach);
  const hydrate = useMissionStore((s) => s.hydrate);
  const applyEvent = useMissionStore((s) => s.applyEvent);
  const setConnection = useMissionStore((s) => s.setConnection);
  const loadDiff = useMissionStore((s) => s.loadDiff);

  const mission = useMissionStore((s) => s.mission);
  const status = useMissionStore((s) => s.status);
  const iteration = useMissionStore((s) => s.iteration);
  const connection = useMissionStore((s) => s.connection);
  const timeline = useMissionStore((s) => s.timeline);
  const terminals = useMissionStore((s) => s.terminals);
  const attemptOrder = useMissionStore((s) => s.attemptOrder);
  const activeTab = useMissionStore((s) => s.activeTerminalTab);
  const setActiveTab = useMissionStore((s) => s.setActiveTerminalTab);
  const tests = useMissionStore((s) => s.tests);
  const reviews = useMissionStore((s) => s.reviews);
  const patches = useMissionStore((s) => s.patches);
  const selectedAttempt = useMissionStore((s) => s.selectedAttempt);
  const diff = useMissionStore((s) => s.diff);
  const diffState = useMissionStore((s) => s.diffState);
  const diffError = useMissionStore((s) => s.diffError);
  const usageByModel = useMissionStore((s) => s.usageByModel);
  const usageOrder = useMissionStore((s) => s.usageOrder);
  const reportedSpend = useMissionStore((s) => s.reportedSpend);

  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setLoad("loading");
    setLoadDetail(null);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    attach(missionId);
    void (async () => {
      try {
        const fetched = await getMission(missionId);
        if (cancelled) return;
        hydrate(fetched);
        setLoad("ready");
      } catch (cause) {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.isNotFound) {
          setLoad("notfound");
          return;
        }
        setLoad("unreachable");
        setLoadDetail(cause instanceof Error ? cause.message : null);
      }
    })();
    void loadDiff(missionId);
    return () => {
      cancelled = true;
    };
  }, [attach, attempt, hydrate, loadDiff, missionId]);

  useEffect(() => {
    if (load !== "ready") return;
    const stream = openMissionStream(missionId, {
      onEvent: applyEvent,
      onStateChange: setConnection,
    });
    return () => stream.close();
  }, [applyEvent, load, missionId, setConnection]);

  // Once the run ends, re-read the mission so attempts and usage match the DB.
  const finished = useMissionStore((s) => s.finished);
  useEffect(() => {
    if (!finished || load !== "ready") return;
    void getMission(missionId).then(hydrate).catch(() => undefined);
  }, [finished, hydrate, load, missionId]);

  const usage = useMemo(
    () =>
      usageOrder
        .map((model) => usageByModel[model])
        .filter((entry) => entry !== undefined),
    [usageByModel, usageOrder],
  );

  const spend = useMemo(() => {
    const summed = usage.reduce((acc, entry) => acc + entry.cost_usd, 0);
    return Math.max(summed, reportedSpend);
  }, [reportedSpend, usage]);

  const running = !isTerminalStatus(status) && load === "ready";
  const hasPatch = diff.length > 0 || Boolean(selectedAttempt);

  if (load === "notfound") {
    return (
      <>
        <AppHeader />
        <main className="archon-grid flex-1 px-4 py-10">
          <div className="mx-auto max-w-2xl">
            <NotFoundState missionId={missionId} />
          </div>
        </main>
      </>
    );
  }

  if (load === "unreachable") {
    return (
      <>
        <AppHeader />
        <main className="archon-grid flex-1 px-4 py-10">
          <div className="mx-auto max-w-2xl">
            <UnreachableState onRetry={retry} detail={loadDetail} />
          </div>
        </main>
      </>
    );
  }

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <AppHeader>
        <CockpitHeader
          missionId={missionId}
          mission={mission}
          status={status}
          iteration={iteration}
          spend={spend}
          connection={connection}
        />
      </AppHeader>

      <main className="grid min-h-0 flex-1 gap-3 overflow-y-auto p-3 lg:grid-cols-[minmax(20rem,32%)_minmax(0,1fr)] lg:overflow-hidden">
        <ReasoningStream
          entries={timeline}
          className="h-[24rem] lg:h-auto lg:min-h-0"
        />
        <div className="grid min-h-0 gap-3 lg:grid-rows-[minmax(0,1fr)_minmax(0,1fr)]">
          <TerminalPanel
            attempts={attemptOrder}
            active={activeTab}
            onSelect={setActiveTab}
            terminals={terminals}
            tests={tests}
            className="h-[20rem] lg:h-auto lg:min-h-0"
          />
          <DiffViewer
            files={diff}
            state={diffState}
            error={diffError}
            attempt={selectedAttempt}
            stats={selectedAttempt ? (patches[selectedAttempt] ?? []) : []}
            tests={selectedAttempt ? tests[selectedAttempt] : undefined}
            review={selectedAttempt ? reviews[selectedAttempt] : undefined}
            onRetry={() => void loadDiff(missionId)}
            className="h-[24rem] lg:h-auto lg:min-h-0"
          />
        </div>
      </main>

      <SummaryBar
        missionId={missionId}
        usage={usage}
        spend={spend}
        running={running}
        hasPatch={hasPatch}
      />
    </div>
  );
}
