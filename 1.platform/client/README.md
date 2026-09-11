# ARCHON Cockpit

The web client for ARCHON. Submits missions to the FastAPI orchestrator and
renders the three live streams — agent reasoning, sandbox terminal, and the
resulting diff — from a single `EventSource`.

Next.js 16 (App Router, Turbopack) · React 19 · Tailwind CSS v4 · Zustand ·
`@monaco-editor/react` · `@xterm/xterm`. Dark theme only.

Monaco is bundled from the local `monaco-editor` package rather than loaded from
jsdelivr, so the diff pane still renders on a network that blocks the CDN. That
is why the client chunks are large.

## Running it

Node 26 and npm 11. Do not use pnpm, yarn, or bun — the lockfile is npm's.

```bash
npm install
cp .env.example .env.local   # then edit
npm run dev                  # http://localhost:3000
```

Without a server running, use mock mode — every `fetch` and `EventSource` is
replaced by an in-browser fake that streams one canned mission:

```bash
NEXT_PUBLIC_ARCHON_MOCK=1 npm run dev
```

### Checks

```bash
npm run lint        # eslint
npm run typecheck   # next typegen && tsc --noEmit
npm run build       # next build (runs typegen + type check itself)
```

`npm run typecheck` shells out to `next typegen` first because the `PageProps<…>`
route helpers live in `.next/types`, which is not committed.

## Environment variables

| Variable | Default | Meaning |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_ARCHON_API` | `http://localhost:8000` | Orchestrator origin. No trailing slash; one is stripped if present. |
| `NEXT_PUBLIC_ARCHON_MOCK` | unset | `1` routes all I/O to `src/mock/` instead of the network. |

Both are `NEXT_PUBLIC_*`, so they are inlined at build time — a container image
built with one API base cannot be repointed at runtime.

The live-mode bearer token is **not** an env var. It lives in `localStorage`
under `archon.demoToken` and is edited from the token control in the header.
Replays never need it.

## Pages

- `/` — mission form (bug healing / migration, SWE-bench instance or GitHub repo,
  optional hint) plus the recorded-run list with a Play button per row.
- `/missions/[id]` — the cockpit. Mission ids prefixed `rp_` render a **REPLAY**
  label in the header; everything else is identical.

## Server contract

Base URL `NEXT_PUBLIC_ARCHON_API`.

| Method | Path | Auth | Notes |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/missions` | bearer | `202 {id, status, stream}` |
| `GET` | `/api/v1/missions/{id}` | — | mission + `attempts[]` + `usage[]` |
| `GET` | `/api/v1/missions/{id}/diff` | — | `[{path, original, modified, language}]` for the selected attempt; `[]` if none |
| `GET` | `/api/v1/missions/{id}/patch` | — | `text/x-patch` download |
| `POST` | `/api/v1/missions/{id}/abort` | bearer | `200` |
| `GET` | `/api/v1/missions/{id}/events` | — | SSE |
| `GET` | `/api/v1/replays` | — | recorded runs |
| `POST` | `/api/v1/replays/{id}/play` | — | `202 {id, status, stream}`, new mission id prefixed `rp_` |
| `GET` | `/api/v1/swe-instances` | — | dropdown source |
| `GET` | `/healthz` | — | `{ok, sandbox_backend, models:{ultra,super,nano}}` |

### SSE events

Every frame carries a monotonic `id:`, so `EventSource` resumes with
`Last-Event-ID` on its own after a drop.

| Event | Data | Rendered as |
| :--- | :--- | :--- |
| `status` | `{status, iteration}` | header pill, iteration counter, reasoning rule |
| `thought` | `{stage, model, text}` | reasoning entry with a model badge |
| `tavily` | `{query, results, ms}` | reasoning entry |
| `terminal` | `{attempt, stream, line}` | xterm tab per `attempt` (`baseline` first) |
| `tests` | `{attempt, exit_code, fail_to_pass, pass_to_pass_broken, total}` | tab dot + patch panel badge |
| `patch` | `{attempt, files:[{path, added, removed}]}` | per-file `+/-` counts |
| `review` | `{attempt, verdict, reasons[]}` | reasoning entry; `APPROVE` selects the attempt and refetches `/diff` |
| `usage` | `{model, prompt_tokens, completion_tokens, cost_usd}` | footer, aggregated per model |
| `error` | `{message}` | reasoning entry |
| `done` | `{status, selected_attempt, iterations, spend_usd}` | closes the stream, refetches `/diff` |

Statuses: `PENDING`, `PROVISIONING`, `REPRODUCING`, `GROUNDING`, `REASONING`,
`TESTING`, `REVIEWING`, `VERIFIED`, `NOTHING_TO_FIX`, `FAILED`, `ABORTED`.

Model badges are derived from the model id, not a server field: `ultra` →
`ULTRA`, `super` → `SUPER`, `nano` → `NANO`, anything else → `MODEL`.

## Layout

```
src/
  app/                    routes only
  components/             UI; cockpit/ holds the four panes
  lib/
    api.ts                REST client, ApiError
    sse.ts                EventSource wrapper
    decode.ts, parse.ts   boundary validation — every wire value is unknown first
    types.ts, format.ts, env.ts, token.ts
  store/mission.ts        Zustand store fed by the event stream
  mock/                   fixtures + fake server, loaded lazily
```

`src/lib` and `src/store` contain no `any`. Every REST payload and SSE frame
goes through `decode.ts`, which coerces rather than throws, so a schema drift on
the server degrades a field instead of blanking the cockpit.

## Mock mode notes

The fake serves one mission: a pydantic v1 → v2 `field_validator` repair over two
iterations, with two candidate attempts running in parallel in iteration 2 and
one approved. Frames stream at ~150 ms. `GET /diff` returns `[]` until the
approval frame, then two files.

One thing mock mode cannot fake: **Download patch** is a plain `<a download>` to
`{API_BASE}/api/v1/missions/{id}/patch`, so it still hits the network and will
fail with no server running.

## Contract details that were interpreted

- `iteration x/5` — the denominator is the 5-iteration ceiling from DESIGN.md §6,
  hardcoded as `MAX_ITERATIONS`. No endpoint reports it.
- Model tiers are inferred from substrings of the model id, since no event
  carries a tier field.
- Terminal tabs are built from the `attempt` values actually seen in `terminal`
  and `patch` frames. `baseline` is pinned first; the rest sort by id, which
  keeps `a_01 … a_NN` in emission order.
- `GET /diff` returns only the *selected* attempt, so the cockpit cannot show a
  per-attempt diff. Terminal tabs are freely switchable; the patch pane always
  follows the server's selection (`review APPROVE`, then `done.selected_attempt`,
  then `attempts[].selected`).
- `spend` is displayed as `max(sum of usage events, spend_usd reported by
  done/GET)` so it can never read lower than the server's own figure.
- The first `usage` frame discards usage seeded from `GET /missions/{id}`. A
  reload mid-run, where the server replays the log from the start, would
  otherwise double-count.
- `Mission.repo_url`, `git_ref`, `test_command`, `swe_instance_id` and
  `done.selected_attempt` are treated as nullable; the spec types them as plain
  strings but a SWE-bench mission has no repo URL and vice versa.
