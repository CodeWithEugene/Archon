"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, createMission, listSweInstances } from "@/lib/api";
import { readDemoToken } from "@/lib/token";
import type { CreateMissionRequest, MissionType, SweInstance } from "@/lib/types";
import { Field, Segmented, SubmitButton } from "./form-controls";

type Source = "swe" | "repo";

const TYPE_HELP: Record<MissionType, string> = {
  BUG_HEALING: "Reproduce a failing suite, then patch until it passes.",
  MIGRATION: "Carry a codebase across a breaking dependency upgrade.",
};

export function MissionForm() {
  const router = useRouter();
  const [type, setType] = useState<MissionType>("BUG_HEALING");
  const [source, setSource] = useState<Source>("swe");
  const [instances, setInstances] = useState<SweInstance[]>([]);
  const [instanceId, setInstanceId] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [gitRef, setGitRef] = useState("main");
  const [testCommand, setTestCommand] = useState("pytest tests/ -x -q");
  const [hint, setHint] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsToken, setNeedsToken] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listSweInstances()
      .then((rows) => {
        if (cancelled) return;
        setInstances(rows);
        setInstanceId((current) => current || (rows[0]?.id ?? ""));
      })
      .catch(() => {
        if (!cancelled) setInstances([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = instances.find((row) => row.id === instanceId);

  function validate(): string | null {
    if (source === "swe") {
      return instanceId ? null : "Pick a SWE-bench instance.";
    }
    if (!/^https:\/\/github\.com\/[^/]+\/[^/]+/.test(repoUrl.trim())) {
      return "Repository must be an https://github.com/owner/repo URL.";
    }
    if (testCommand.trim().length === 0) return "A test command is required.";
    return null;
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const problem = validate();
    setNeedsToken(false);
    if (problem) {
      setError(problem);
      return;
    }

    const body: CreateMissionRequest =
      source === "swe"
        ? { type, swe_instance_id: instanceId }
        : {
            type,
            repo_url: repoUrl.trim(),
            git_ref: gitRef.trim() || "main",
            test_command: testCommand.trim(),
            swe_instance_id: null,
          };
    if (hint.trim().length > 0) body.hint = hint.trim();

    setSubmitting(true);
    setError(null);
    try {
      const created = await createMission(body, readDemoToken());
      router.push(`/missions/${created.id}`);
    } catch (cause) {
      setSubmitting(false);
      if (cause instanceof ApiError && cause.isUnauthorized) {
        setNeedsToken(true);
        setError(
          "Live mode rejected the request. Open the token control in the header and paste a demo token, or play a recorded run instead.",
        );
        return;
      }
      setError(
        cause instanceof Error ? cause.message : "Could not start the mission.",
      );
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <Field label="Mission type" hint={TYPE_HELP[type]}>
        <Segmented
          name="mission-type"
          value={type}
          onChange={(next) => setType(next as MissionType)}
          options={[
            { value: "BUG_HEALING", label: "Bug healing" },
            { value: "MIGRATION", label: "Migration" },
          ]}
        />
      </Field>

      <Field label="Target">
        <Segmented
          name="mission-source"
          value={source}
          onChange={(next) => setSource(next as Source)}
          options={[
            { value: "swe", label: "SWE-bench instance" },
            { value: "repo", label: "GitHub repository" },
          ]}
        />
      </Field>

      {source === "swe" ? (
        <Field
          label="Instance"
          htmlFor="swe-instance"
          hint={selected?.short_problem}
        >
          <select
            id="swe-instance"
            value={instanceId}
            onChange={(event) => setInstanceId(event.target.value)}
            disabled={instances.length === 0}
            className="w-full border border-line-strong bg-bg px-3 py-2 font-mono text-[13px] text-text disabled:text-faint"
          >
            {instances.length === 0 ? (
              <option value="">No instances available</option>
            ) : null}
            {instances.map((row) => (
              <option key={row.id} value={row.id}>
                {row.id} — {row.repo}
              </option>
            ))}
          </select>
        </Field>
      ) : (
        <div className="grid gap-4 sm:grid-cols-[1fr_10rem]">
          <Field label="Repository URL" htmlFor="repo-url">
            <input
              id="repo-url"
              value={repoUrl}
              onChange={(event) => setRepoUrl(event.target.value)}
              placeholder="https://github.com/owner/repo"
              spellCheck={false}
              className="w-full border border-line-strong bg-bg px-3 py-2 font-mono text-[13px] text-text placeholder:text-faint"
            />
          </Field>
          <Field label="Git ref" htmlFor="git-ref">
            <input
              id="git-ref"
              value={gitRef}
              onChange={(event) => setGitRef(event.target.value)}
              placeholder="main"
              spellCheck={false}
              className="w-full border border-line-strong bg-bg px-3 py-2 font-mono text-[13px] text-text placeholder:text-faint"
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Test command" htmlFor="test-command">
              <input
                id="test-command"
                value={testCommand}
                onChange={(event) => setTestCommand(event.target.value)}
                spellCheck={false}
                className="w-full border border-line-strong bg-bg px-3 py-2 font-mono text-[13px] text-text placeholder:text-faint"
              />
            </Field>
          </div>
        </div>
      )}

      <Field
        label="Hint"
        htmlFor="hint"
        optional
        hint="Paste a stack trace or a one-line steer. Treated as untrusted input."
      >
        <textarea
          id="hint"
          value={hint}
          onChange={(event) => setHint(event.target.value)}
          rows={3}
          spellCheck={false}
          className="w-full resize-y border border-line-strong bg-bg px-3 py-2 font-mono text-[12px] leading-relaxed text-text placeholder:text-faint"
          placeholder="ImportError: cannot import name 'validator' from 'pydantic'"
        />
      </Field>

      {error ? (
        <p
          role="alert"
          className={`border px-3 py-2 text-[12px] leading-relaxed ${
            needsToken
              ? "border-warn/50 bg-warn/10 text-warn"
              : "border-bad/50 bg-bad/10 text-bad"
          }`}
        >
          {error}
        </p>
      ) : null}

      <SubmitButton pending={submitting}>Start mission</SubmitButton>
    </form>
  );
}
