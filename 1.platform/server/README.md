# ARCHON Server

FastAPI orchestrator for sandbox-verified software repair. Routes model calls across NVIDIA Nemotron 3 tiers on Nebius Token Factory, executes all repository code in Token Factory Sandboxes, and streams every step over Server-Sent Events.

## Run locally

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in keys, or leave empty and use the fake backends below
uvicorn app.main:app --reload --port 8000
```

`GET /healthz` reports which backends are active and any configuration problems.

## Backends

| Variable | Values | Notes |
| :--- | :--- | :--- |
| `ARCHON_LLM_BACKEND` | `nebius` (default), `fake` | `fake` returns scripted responses; used in tests. |
| `ARCHON_SANDBOX_BACKEND` | `contree` (default), `local`, `fake` | `contree` is Token Factory Sandboxes via `contree-sdk` and needs `NEBIUS_API_KEY` plus `NEBIUS_PROJECT_ID`. `local` runs repository code on this machine in copy-on-fork directories; development only, refused in production. |

Development without credits: `ARCHON_ULTRA_MODEL=nvidia/nemotron-3-super-120b-a12b` routes patch generation to Super.

## Layout

```
app/
  main.py          app factory, wiring, lifespan
  settings.py      typed env config
  api/             missions, events (SSE), replays, swe catalog, pricing, health
  core/            models, runner (state machine), events bus, router, scoring, patches, pricing, registry
  llm/             Nebius client (OpenAI SDK), prompt builders with untrusted-context delimiters
  roles/           researcher, engineer, reviewer, compactor/narrator
  grounding/       Tavily wrapper with timeout and cache
  sandbox/         backend protocol, contree, local, fake, pytest parser, high-level service
  missions/        migration scan and parity sample, SWE-bench catalog
  replay/          recorder and player
  store/           SQLite
pricing.json       list prices used for cost accounting and estimates
tests/
  unit/            fake backends; runs offline
  integration/     live Nebius, Tavily, Sandboxes; skipped without keys
  golden/          fixtures, instances.json, recordings for replay mode
```

## Tests

```bash
pytest tests/unit -q -m "not slow"     # offline, seconds
pytest tests/unit -q -m slow           # runs the broken_pydantic_v2 fixture through the local backend
pytest tests/integration -q            # needs NEBIUS_API_KEY, NEBIUS_PROJECT_ID, TAVILY_API_KEY
ruff check app tests && ruff format --check app tests && mypy app
```

## Mission flow

PENDING → PROVISIONING (clone, install) → REPRODUCING (baseline tests) → GROUNDING (Tavily, or repo scan for migrations) → REASONING (Ultra: root cause + candidates) → TESTING (one sandbox fork per candidate) → REVIEWING (Super) → VERIFIED. Any step can go to ABORTED on user abort or spend cap, or FAILED after the iteration limit. See `0.docs/build/DESIGN.md`.
