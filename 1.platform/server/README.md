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

Development without credits: `ARCHON_ULTRA_MODEL=nvidia/nemotron-3-super-120b-a12b` routes patch generation to Super. Real IDs and prices (verified September 12): Ultra `nvidia/Nemotron-3-Ultra-550b-a55b` $1/$3, Super `nvidia/nemotron-3-super-120b-a12b` $0.30/$0.90, Nano `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` $0.06/$0.24 per 1M tokens.

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

## SWE-bench Verified instances

Instances come from the Sandboxes public catalog (`swebench/sweb.eval.x86_64.<owner>_1776_<repo>-<n>:latest`). Add one:

```bash
python -m tests.golden.fetch_swe psf__requests-2317        # writes tests/golden/swe/<id>.json, updates instances.json
python -m tests.golden.run --swe psf__requests-2317 --llm nebius --backend contree --record
```

The runner boots the preloaded image, applies the instance's test patch, runs only its FAIL_TO_PASS and PASS_TO_PASS ids under `conda activate testbed`, and gives the engineer the problem statement, the failing test source, and the repository file list. Recordings land in `tests/golden/recordings/` and appear in the cockpit's replay list.

## Tests

```bash
pytest tests/unit -q -m "not slow"     # offline, seconds
pytest tests/unit -q -m slow           # runs the broken_pydantic_v2 fixture through the local backend
pytest tests/integration -q            # needs NEBIUS_API_KEY, NEBIUS_PROJECT_ID, TAVILY_API_KEY
ruff check app tests && ruff format --check app tests && mypy app
```

## Mission flow

PENDING → PROVISIONING (clone, install) → REPRODUCING (baseline tests) → GROUNDING (Tavily, or repo scan for migrations) → REASONING (Ultra: root cause + candidates) → TESTING (one sandbox fork per candidate) → REVIEWING (Super) → VERIFIED. Any step can go to ABORTED on user abort or spend cap, or FAILED after the iteration limit. See `0.docs/build/DESIGN.md`.
