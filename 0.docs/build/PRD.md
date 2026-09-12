# ARCHON — Product Requirements Document

> **Version:** 2.0.0 (revised after the September 11 audit)
> **Status:** Draft. Nothing is frozen until Sandboxes beta access is confirmed and one end-to-end run exists.
> **Event:** Nebius x NVIDIA Global AI Hackathon, Track 1: Coding and Agentic Engineering
> **Awards in scope:** one Overall or Track award, plus Best Use of Tavily as the single bonus award

---

## 1. Summary

ARCHON is an autonomous repair agent. Given a repository and a failing test command, it reproduces the failure inside a Nebius Token Factory Sandbox, grounds itself in current documentation through the Tavily Search API, uses NVIDIA Nemotron 3 Ultra to diagnose and patch the code, and re-runs the tests inside the sandbox until they pass. Every candidate patch is tried on its own sandbox fork. The result is a diff the user can trust because the tests that prove it ran in front of them.

The same loop drives a second mission type: migrating a codebase from the OpenAI or Anthropic SDK to Nebius Token Factory and Nemotron, verified by the repository's own tests plus a small parity harness.

### Vision

Show that an open model on open infrastructure can run a complete, verified software-repair loop, and that the sandbox is what makes the output trustworthy.

---

## 2. Problem

**Dependency and CI breakage is constant and tedious.** A library publishes a breaking release, a transitive dependency drifts, a runtime version changes, and the test suite goes red. Diagnosing it means reading stack traces, reading changelogs, and trying fixes. Most of that work is mechanical.

**Chat assistants cannot close the loop.** Pasting a stack trace into a chatbot produces a plausible fix that nobody has executed. The model's training data predates the release that caused the break, so it often suggests arguments that no longer exist. The developer still has to apply the patch, run the tests, and iterate.

**Running model-generated code locally is unsafe.** An agent that installs packages and executes tests needs isolation. Without it, teams either refuse to let the agent run anything or accept the risk.

**Migrating off a closed LLM provider is a real but underserved task.** Teams that want to move to open models on Nebius face client rewrites, model-name mapping, tool-schema differences, and the problem that their existing tests mock the LLM and therefore prove nothing about behavioral parity.

---

## 3. Audience

| Role | Situation | What ARCHON gives them |
| :--- | :--- | :--- |
| Backend or platform engineer | CI is red after a dependency update and they are the one on call. | Paste the repo and the test command, watch the agent reproduce, research, patch, and verify. Download the patch. |
| Open-source maintainer | Issue backlog full of "tests fail on version X" reports. | Point ARCHON at the failing instance. Get a verified patch and the full reasoning trace to review. |
| AI engineering lead | Wants to try Nemotron on Nebius but the codebase is wired to a closed SDK. | Run a migration mission. Get a diff, a parity report, and a cost estimate from current list prices. |

---

## 4. Scope

### 4.1 In scope

- **Bug-healing missions** on public GitHub repositories and on SWE-bench Verified instances from the Sandboxes catalog.
- **Migration missions** for Python codebases using the `openai` or `anthropic` SDKs. TypeScript is a stretch goal.
- **Sandbox execution** of clone, install, and test commands through Token Factory Sandboxes, with one fork per candidate patch and best-of-N selection.
- **Tavily grounding** inside the loop: query synthesis from the error signature, search, and injection of results as delimited context.
- **Model routing** across Nemotron 3 Ultra, Super, and Nano by task type.
- **Cockpit UI**: mission form, live reasoning stream, live sandbox terminal, side-by-side diff, patch download.
- **Public demo** with a replay mode and a token-gated live mode.

### 4.2 Out of scope for the hackathon

- Dependency modernization as a separate mission type. It is covered by bug healing when the upgrade breaks tests.
- Tree-sitter indexing, a vector index, or any persistent memory. Ripgrep plus targeted file reads is sufficient for the loop.
- Pushing branches or opening pull requests on the user's behalf. Patches are downloaded and applied with `git apply`.
- Any observability beyond the cockpit event log and optional LangSmith tracing (added September 12; on only when `LANGSMITH_API_KEY` is set).
- Bedrock, Cohere, or LangChain provider adapters for migration.
- Replacing human code review. ARCHON produces a verified patch; a human merges it.

---

## 5. Functional requirements

### FR-1 Mission intake
- **FR-1.1** Accept a public `https://github.com/<owner>/<repo>` URL with an optional git ref, an optional subproject path for monorepos, plus a test command. Reject any other URL scheme and any filesystem path.
- **FR-1.2** Accept a SWE-bench Verified instance ID and resolve it to the preloaded Sandboxes environment.
- **FR-1.3** Accept a mission type: `BUG_HEALING` or `MIGRATION`.
- **FR-1.4** Accept an optional pasted stack trace or CI log to seed the diagnosis.

### FR-2 Sandbox execution
- **FR-2.1** All clone, install, and test commands run inside Token Factory Sandboxes via `contree-sdk`. Nothing from the target repository executes on the ARCHON server.
- **FR-2.2** After the baseline reproduction, the resulting image is checkpointed. Every candidate patch runs on a fork of that checkpoint.
- **FR-2.3** Sandbox stdout and stderr are streamed to the client as they arrive.
- **FR-2.4** Each command has a configurable wall-clock limit, default 15 minutes, enforced by cancelling the sandbox operation.

### FR-3 Bug-healing loop
- **FR-3.1** Run the test command on the baseline and record exit code, failing test IDs, and passing test IDs.
- **FR-3.2** If the baseline already passes, stop and report that there is nothing to fix.
- **FR-3.3** Extract the error signature and library names, synthesize Tavily queries, and fetch results.
- **FR-3.4** Send the failing tests, relevant source excerpts, and Tavily context to Nemotron 3 Ultra to produce a root-cause note and up to N candidate patches, N default 2.
- **FR-3.5** Apply each candidate on its own fork, run the tests, and score by: failing tests fixed, previously passing tests still passing, patch size.
- **FR-3.6** If no candidate passes, feed the best candidate's test output back into the next iteration. Maximum 5 iterations.
- **FR-3.7** A patch is presented as verified only if the originally failing tests pass and no originally passing test fails.

### FR-4 Migration loop
- **FR-4.1** Locate `openai` and `anthropic` client construction, model-name literals, and tool or function-calling definitions using ripgrep and file reads.
- **FR-4.2** Rewrite client construction to `base_url=https://api.tokenfactory.nebius.com/v1/` with `NEBIUS_API_KEY`. For the Anthropic Messages API, rewrite to the OpenAI-compatible chat completions shape.
- **FR-4.3** Map model names using a table in the repo: reasoning-tier names to `nvidia/Nemotron-3-Ultra-550b-a55b`, mid-tier to `nvidia/nemotron-3-super-120b-a12b`, small-tier to `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.
- **FR-4.4** Run the repository's tests in the sandbox. Additionally run a parity harness of 5 to 10 prompts against the original provider's recorded responses and the new Nemotron responses, reporting a similarity score. State clearly in the UI that mocked tests do not prove parity.
- **FR-4.5** Produce a cost estimate from `pricing.json`, a maintained table of current list prices with a last-updated date, using a stated input-to-output ratio. Never present it as a guarantee.

### FR-5 Grounding
- **FR-5.1** Call the Tavily Search API with `search_depth="advanced"` and a 10-second timeout. On timeout or error, continue the loop without grounding and record that fact in the trace.
- **FR-5.2** Insert Tavily results into prompts inside a clearly delimited untrusted-context block.

### FR-6 Cockpit
- **FR-6.1** Next.js 16 application, dark theme, responsive down to tablet width.
- **FR-6.2** Reasoning stream showing stage, model in use, and content, over Server-Sent Events.
- **FR-6.3** Sandbox terminal using xterm.js fed by the same SSE channel.
- **FR-6.4** Diff viewer using Monaco showing side-by-side changes per file, with the test result badge.
- **FR-6.5** "Download patch" button producing a `.patch` file and a copyable `git apply` command.
- **FR-6.6** Mission summary card: iterations used, tests before and after, tokens per model, estimated spend.

### FR-7 Public demo
- **FR-7.1** Replay mode is the default. It streams recorded traces from the golden dataset and makes no paid calls.
- **FR-7.2** Live mode requires `ARCHON_DEMO_TOKEN`, is rate-limited, and honors `ARCHON_MAX_MISSION_USD`.

---

## 6. Non-functional requirements

| ID | Area | Requirement |
| :--- | :--- | :--- |
| NFR-1 | Security | API keys exist only in server environment variables. The client never receives them. |
| NFR-2 | Isolation | No target-repository code executes outside Token Factory Sandboxes. |
| NFR-3 | Cost control | Per-mission token accounting per model, and a hard spend cap that aborts the mission. |
| NFR-4 | Reliability | Sandbox timeouts, Tavily failures, and model rate limits produce a readable failure report rather than a hung mission. |
| NFR-5 | Concurrency | Async FastAPI; at least 3 concurrent missions without blocking. |
| NFR-6 | Availability | Public demo stays up in replay mode from submission through December 15, 2026. |
| NFR-7 | Reproducibility | Every golden-dataset run is recorded and replayable from the repo. |

---

## 7. Acceptance scenarios

### Scenario A: SWE-bench Verified repair
1. User selects a SWE-bench Verified instance from a dropdown.
2. ARCHON spawns the preloaded sandbox and runs the fail-to-pass tests. Terminal shows the failure.
3. Tavily queries appear in the stream with result counts.
4. Nemotron 3 Ultra emits a root-cause note and two candidate patches. Two forks run in parallel in the terminal.
5. One fork passes. The diff viewer shows the patch with a green badge listing fail-to-pass and pass-to-pass counts.
6. User downloads the patch.

### Scenario B: Migration of a small OpenAI-based service
1. User submits a public repo URL that uses the `openai` SDK and its test command.
2. ARCHON lists every client construction and model literal it found.
3. Nemotron 3 Ultra produces the migration patch. The sandbox runs the repository tests.
4. The parity harness runs and reports a similarity score with the caveat about mocked tests.
5. The cost card shows the estimate, the price table date, and the assumptions.

---

## 8. Success metrics

| Metric | Target | How measured |
| :--- | :--- | :--- |
| Golden-dataset resolve rate | At least 5 of 10 SWE-bench Verified instances | Fail-to-pass tests pass and pass-to-pass tests still pass, recorded in the repo |
| Regressions introduced | 0 on any presented patch | Pass-to-pass check in FR-3.7 |
| Median iterations to resolve | 3 or fewer | Mission records |
| Median cost per resolved mission | Under $2 on Ultra list prices | Token accounting per mission |
| Demo uptime during judging | 100% in replay mode | Uptime monitor |
