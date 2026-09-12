# ARCHON — Sessions and Decision Log

> Running journal for the build. Each session records what was done, what was decided and why, what blocked, and what is next. Architectural Decision Records (ADRs) live here and are numbered once; superseded ADRs are marked, not deleted.

---

## Session 0 — September 11, 2026 (afternoon): Research and first specification

**Done**
1. Read the Devpost overview, rules, and resources pages. Recorded tracks, prizes, dates, judging criteria, and credits in [../info.md](../info.md).
2. Created the repository skeleton, Apache 2.0 license, [CONTRIBUTING.md](../../CONTRIBUTING.md), [SECURITY.md](../../SECURITY.md).
3. Wrote the first versions of [../problem+solution.md](../problem+solution.md), [PRD.md](PRD.md), [DESIGN.md](DESIGN.md), [AGENTS.md](AGENTS.md), [PLAN.md](PLAN.md), [TESTING.md](TESTING.md), and [../prior-art.md](../prior-art.md).

---

## Session 1 — September 11, 2026 (evening): Audit and correction

**Done**
1. Full audit of every document against the live Devpost pages, Nebius Token Factory docs, Sandboxes docs, NVIDIA model cards, and current vendor pricing.
2. Corrected every model ID to the real Token Factory identifiers. Removed references to the 2024 Llama-3.1-Nemotron-70B model.
3. Rewrote the sandbox design around Token Factory Sandboxes and `contree-sdk` instead of a self-managed Docker design.
4. Removed false completion claims from the README checklist and PLAN milestones. Nothing in `1.platform/` exists yet and the docs now say so.
5. Cut scope (ADR-005). Replaced unsourced statistics with sourced pricing. Removed self-scoring and hype language.
6. Added `.gitignore`, removed a stray empty directory, filled empty READMEs, created [../../2.submission/FEEDBACK.md](../../2.submission/FEEDBACK.md).
7. Fixed absolute `file:///` links that were broken on GitHub.

**Blockers**
- Sandboxes beta access not yet requested. This is the first task of Session 2.
- Nemotron 3 Nano exact model ID not yet confirmed against `GET /v1/models`.
- Nebius list price for Ultra taken from a third-party catalog; needs confirmation on the Token Factory pricing page.

**Next**
1. Request Sandboxes beta access. Claim both $25 credits.
2. Run `GET /v1/models?verbose=true`, record IDs and prices in `pricing.json`.
3. Week 1 spike per [PLAN.md](PLAN.md): FastAPI scaffold, one Nemotron call, one sandbox run.

---

## Session 2 — September 11, 2026 (night): Server build

**Done**
1. Scaffolded `1.platform/server`: FastAPI app, typed settings, SQLite store, event bus, SSE endpoint with `Last-Event-ID` resume.
2. Installed and introspected `contree-sdk` 0.3.6. The docs lag the package: `Contree(token=, base_url=)` also needs `NEBIUS_PROJECT_ID`; `image.run(shell=, timeout=, files=, disposable=False)` creates fork points; results expose `exit_code`, `stdout`, `stderr`, `cost`, and the new image `uuid`. `ContreeBackend` is written against the real API.
3. Three sandbox backends behind one protocol: `contree` (Token Factory Sandboxes), `local` (development only, copy-on-fork directories, refused in production), `fake` (scripted, for tests).
4. Mission runner implementing the full state machine: provision, baseline, Tavily grounding, Ultra diagnose-and-patch, N candidates on N forks, scoring (no pass-to-pass regressions first), reviewer, spend cap, abort, failure report, recording.
5. Migration mission: ripgrep scan, model mapping from `pricing.json`, cost estimate, model-level parity sample with the honest caveat.
6. Roles: researcher, engineer (with `files_to_read` rounds), reviewer (deterministic safety checks then Super), compactor, narrator.
7. Test parsing: JUnit XML written inside the sandbox, text fallback. Found and fixed the `pytest -q` gap where passing tests were not counted.
8. 43 unit tests, ruff and mypy strict clean, GitHub Actions CI. Golden runner (`tests/golden/run.py`) proves the loop end to end on the local backend with a scripted model.
9. Three fixture repositories for the golden set: `broken_pydantic_v2` (4 of 6 tests fail, reference patch fixes all 6), `openai_chat_service`, `anthropic_summarizer`.
10. Client cockpit built (`1.platform/client`, Next.js 16, Zustand, Monaco, xterm) and verified in the browser against the live server: replay of the recorded local run renders the reasoning stream, per-attempt terminal tabs, reviewer verdict, per-model token totals, Monaco diff, and patch download. Fixed a duplicate-tab reducer bug found in that walkthrough.
11. Development launch configs: `1.platform/server/scripts/dev.sh` (offline backends by default) and `.claude/launch.json`. Dev server uses port 8010 because 8000 was taken on this machine.

**Decisions**
- ADR-008: the supervisor is deterministic code, not a model. Super narrates optionally. See AGENTS.md 2.1.
- ADR-009: test results come from a JUnit report produced inside the sandbox, never from parsing terminal text alone.

**Blockers**
- Sandboxes beta access requested; `ContreeBackend` is untested against the live API until it arrives.
- No `NEBIUS_API_KEY` or `TAVILY_API_KEY` in this environment; live integration tests are written and skip cleanly.

**Next**
1. When keys arrive: `pytest tests/integration -q`, then `python -m tests.golden.run --fixture broken_pydantic_v2 --llm nebius --backend local --record`.
2. When Sandboxes access arrives: run the week-1 gate test in `tests/integration/test_live.py`, then pick 10 SWE-bench Verified instances and fill `tests/golden/instances.json`.
3. Live-stream terminal lines from Sandboxes operations instead of emitting them after each command completes.

---

## Session 3 — September 12, 2026: Keys, Tavily CLI, LangSmith tracing

**Done**
1. Nebius Builders application accepted. `.env` populated with `TAVILY_API_KEY` and `LANGSMITH_API_KEY` (Nebius key and project id still pending).
2. Followed Tavily's agent-setup skill: Tavily CLI 0.1.8 installed and authenticated with the project key, eight Tavily agent skills installed globally for Claude Code, live search verified through the CLI and through `tests/integration/test_live.py::test_tavily_search`.
3. Installed the LangSmith skills (`langsmith-trace`, `langsmith-dataset`, `langsmith-evaluator`) and the `langsmith` CLI globally. Verified the key against the LangSmith API.
4. Added tracing per the `langsmith-trace` skill: `wrap_openai` on the Nebius client, `@traceable` spans on every role, sandbox operation, Tavily search, and the mission root, with input/output scrubbing. Key-gated; six unit tests.

5. First live Nebius calls. Verified the real model IDs and prices from `GET /v1/models?verbose=true`: Ultra `nvidia/Nemotron-3-Ultra-550b-a55b` $1/$3, Super `nvidia/nemotron-3-super-120b-a12b` $0.30/$0.90, Nano `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` $0.06/$0.24, plus `nvidia/Nemotron-3_5-Lightning` at Nano prices with 1M context. Corrected every ID in code and docs; `pricing.json` now marks Nebius prices verified.
6. Found that Nemotron 3 reasons before answering and can return empty `content` when the budget is small. Added `enable_thinking` control per task (on for patch synthesis, off elsewhere) and a retry that doubles the budget when reasoning is truncated.
7. Sandboxes: authentication works, but the key has no Sandboxes permissions yet (all `false` in `whoami`). Beta access still needs to be granted for the project.
8. The pasted `NEBIUS_API_KEY` was a short-lived IAM token (expiry within hours). A long-lived Token Factory API key is required.

**Decisions**
- ADR-011: thinking is a per-task routing decision, not a global switch. Ultra thinks for patches; Super and Nano answer directly for research, review, and compaction.
- ADR-010: LangSmith tracing is in scope after all, as an optional key-gated layer. ADR-005's cut still applies to LangSmith as a required dependency: without the key nothing changes.

**Blockers**
- Need a long-lived Token Factory API key in `.env` (the current value is a short-lived IAM token).
- Sandboxes beta permissions not yet granted for `NEBIUS_PROJECT_ID`.

---

## Architectural Decision Records

### ADR-001: Track selection
- **Decision:** Track 1, Coding and Agentic Engineering. One track only.
- **Rationale:** The track description names agents that write, run, and test code in Token Factory Sandboxes. The rules allow exactly one track per project; the earlier note about "secondary eligibility" for Track 2 was incorrect and is withdrawn.

### ADR-002: Model routing by tier (revised in Session 1)
- **Decision:**
  - `nvidia/Nemotron-3-Ultra-550b-a55b`: diagnosis and patch generation, once per iteration.
  - `nvidia/nemotron-3-super-120b-a12b`: supervisor, researcher, reviewer.
  - `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`: log compaction and test-output parsing. Confirm ID.
- **Rationale:** Super is positioned by NVIDIA for orchestration and tool use; putting the supervisor on Ultra contradicted that and quadrupled cost. Development runs override Ultra to Super.
- **Supersedes:** the Session 0 version that placed four roles on Ultra and referenced Llama-3.1-Nemotron-70B.

### ADR-003: Tavily grounding inside the loop
- **Decision:** Call Tavily before the first patch attempt in every mission, with a 10-second timeout, and continue without grounding on failure.
- **Rationale:** Breaking changes are usually newer than training data. Grounding is also the qualifying condition for the Best Use of Tavily award.

### ADR-004: Execution in Token Factory Sandboxes via `contree-sdk` (revised in Session 1)
- **Decision:** All repository code runs in Nebius-hosted Sandboxes. One fork per candidate patch. No rollback; losing forks are dropped.
- **Rationale:** Sandboxes are the product the track names, they are VM-isolated, they ship SWE-bench Verified environments, and forking is the natural fit for best-of-N repair. A self-managed Docker design would have been more work and less aligned.
- **Supersedes:** the Session 0 "Docker/microVM with memory caps" decision.

### ADR-005: Scope cut
- **Decision:** Two mission types (bug healing, migration). Cut: dependency-modernization mode, Tree-sitter indexing, vector index, LangSmith, GitHub PR dispatch with user tokens, TypeScript migration (stretch only).
- **Rationale:** One developer, seven weeks, $50 of inference credit. The cut list and gates are in [PLAN.md](PLAN.md).

### ADR-006: Replay mode for the public demo
- **Decision:** The public demo defaults to replaying recorded golden-dataset missions. Live mode requires a bearer token and a per-mission spend cap.
- **Rationale:** The demo must stay up through December 15 on a small credit budget, and an unauthenticated endpoint that spends Ultra tokens would be drained.

### ADR-008: Deterministic supervisor
- **Decision:** Mission control flow is code. Models are called only inside roles (research, patch, review, compaction, optional narration).
- **Rationale:** Cheaper, testable offline with fakes, and every decision is explainable from the state machine.

### ADR-009: JUnit for test results
- **Decision:** Test commands get `--junitxml` appended when they are pytest, and the report is read back from the result image. Terminal text is a fallback.
- **Rationale:** `pytest -q` hides PASSED lines and the decorated summary; text parsing under-counted passing tests in the first real run.

### ADR-007: Honest metrics
- **Decision:** No fixed cost-saving percentage in docs or UI. Estimates are computed from `pricing.json` with its date shown. Golden-dataset results are reported as the actual resolved count.
- **Rationale:** Judges are engineers. Sourced estimates are more persuasive than round numbers.

---

## Template

```markdown
## Session N — YYYY-MM-DD: Title

**Done**
1.

**Decisions**
- ADR-00X: ...

**Blockers**
-

**Next**
1.
```
