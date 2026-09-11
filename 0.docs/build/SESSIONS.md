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

## Architectural Decision Records

### ADR-001: Track selection
- **Decision:** Track 1, Coding and Agentic Engineering. One track only.
- **Rationale:** The track description names agents that write, run, and test code in Token Factory Sandboxes. The rules allow exactly one track per project; the earlier note about "secondary eligibility" for Track 2 was incorrect and is withdrawn.

### ADR-002: Model routing by tier (revised in Session 1)
- **Decision:**
  - `nvidia/nemotron-3-ultra-550b-a55b`: diagnosis and patch generation, once per iteration.
  - `nvidia/nemotron-3-super-120b-a12b`: supervisor, researcher, reviewer.
  - `nvidia/nemotron-3-nano-30b-a3b`: log compaction and test-output parsing. Confirm ID.
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
