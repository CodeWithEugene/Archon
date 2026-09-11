# Contributing

ARCHON is a submission to the Nebius x NVIDIA Global AI Hackathon. Contributions are welcome as long as they respect the hackathon rules: all code must be original or properly licensed, and the project must keep running on Nebius Token Factory with NVIDIA open models.

## Layout

```
0.docs/            Research and design documents
  build/           PRD, DESIGN, AGENTS, PLAN, TESTING, SESSIONS
1.platform/
  client/          Next.js 16 cockpit
  server/          FastAPI orchestrator
2.submission/      Devpost text and the developer feedback log
```

## Workflow

- `main` is what gets submitted. Work on branches named `feat/...`, `fix/...`, `docs/...`, or `chore/...`.
- Conventional Commits: `feat(server): add sandbox fork per candidate`, `fix(client): reconnect SSE on drop`, `docs(plan): move golden set to week 5`.
- Open a pull request with what changed, why, any new environment variables, and how you verified it.
- Update [0.docs/build/SESSIONS.md](0.docs/build/SESSIONS.md) at the end of every working session.
- When you hit friction with Nebius, Sandboxes, or Nemotron, add a row to [2.submission/FEEDBACK.md](2.submission/FEEDBACK.md) the same day.

## Secrets

Never commit `.env` files or keys. Copy `.env.example` to `.env` and fill it locally. The keys in use are `NEBIUS_API_KEY`, `TAVILY_API_KEY`, and `ARCHON_DEMO_TOKEN`.

## Before you push

```bash
cd 1.platform/server && ruff check . && ruff format --check . && mypy --strict app/ && pytest tests/unit -q
cd 1.platform/client && npm run lint && npx tsc --noEmit
```

Integration tests need real keys and are skipped without them. See [0.docs/build/TESTING.md](0.docs/build/TESTING.md).

## Scope discipline

The plan has a cut list. If a change adds a dependency, a service, or a mission type that is not in [0.docs/build/PLAN.md](0.docs/build/PLAN.md), raise it in the PR description first.
