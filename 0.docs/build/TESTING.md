# ARCHON — Testing Strategy

> **Version:** 2.0.0 (revised after the September 11 audit)
> **Principle:** a patch is shown as verified only when the originally failing tests pass and the originally passing tests still pass, inside a Token Factory Sandbox, on a fork nobody else touched.

---

## 1. Layers

| Layer | What it covers | Runs where | Cost |
| :--- | :--- | :--- | :--- |
| 1. Static | Ruff, mypy strict, ESLint, `tsc --noEmit` | CI, every push | Free |
| 2. Unit | Router, prompt builders, patch JSON validation, pytest output parser, scoring, state machine | CI, every push, all external calls mocked | Free |
| 3. Integration | Live Token Factory call, live Tavily call, live Sandboxes spawn and run | Manual and nightly, real keys | Cents |
| 4. Golden | 10 SWE-bench Verified instances and 2 migration fixtures, end to end on Ultra | Manual, week 5, recorded | Dollars |

---

## 2. Static

```bash
cd 1.platform/server && ruff check . && ruff format --check . && mypy --strict app/
cd 1.platform/client && npm run lint && npm run typecheck
```

---

## 3. Unit tests (`1.platform/server/tests/unit`)

All network clients are replaced with fakes. Nothing here needs a key.

**`test_router.py`**
- Patch generation routes to the Ultra ID; supervision and review to Super; log compaction to Nano.
- `ARCHON_ULTRA_MODEL` override is honored in development.

**`test_prompts.py`**
- Tavily content and repository excerpts land inside the untrusted-context delimiters and never in the system message.
- The previous attempt's output is included only when present.

**`test_patch_schema.py`**
- Valid engineer JSON parses. Missing `root_cause`, more than two candidates, or non-string patches are rejected.
- A response with `files_to_read` and no candidates is accepted and flagged as a read request.

**`test_pytest_parser.py`**
- Parses `-q` and `-v` output into passed, failed, and errored test IDs. Handles `no tests ran` and collection errors.

**`test_scoring.py`**
- An attempt that breaks any pass-to-pass test is never selected over one that does not.
- Ties on fail-to-pass count are broken by smaller patch.

**`test_state_machine.py`**
- Baseline exit 0 leads to `NOTHING_TO_FIX`.
- Five failed iterations lead to `FAILED` with a report containing every attempt.
- Exceeding the spend cap from any state leads to `ABORTED`.
- Reviewer rejection returns to `REASONING` and increments the iteration.

**`test_input_validation.py`**
- `https://github.com/owner/repo` accepted. `file:///`, `http://`, and arbitrary hosts rejected. Unknown SWE-bench IDs rejected.

**`test_pricing.py`**
- `pricing.json` loads, every model in the routing table has a price, and the estimate function returns the expected number for a fixed token count and ratio.

---

## 4. Integration tests (`tests/integration`)

Skipped automatically when the relevant key is absent.

**Token Factory**

```python
import os, pytest
from openai import AsyncOpenAI

pytestmark = pytest.mark.skipif(not os.getenv("NEBIUS_API_KEY"), reason="no key")

@pytest.mark.asyncio
async def test_super_responds():
    client = AsyncOpenAI(base_url=os.environ["NEBIUS_BASE_URL"], api_key=os.environ["NEBIUS_API_KEY"])
    r = await client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=[{"role": "user", "content": "Reply with exactly: PING_OK"}],
        max_tokens=8,
    )
    assert "PING_OK" in (r.choices[0].message.content or "")

@pytest.mark.asyncio
async def test_models_endpoint_lists_nemotron_ids():
    client = AsyncOpenAI(base_url=os.environ["NEBIUS_BASE_URL"], api_key=os.environ["NEBIUS_API_KEY"])
    ids = {m.id for m in (await client.models.list()).data}
    assert "nvidia/Nemotron-3-Ultra-550b-a55b" in ids
    assert "nvidia/nemotron-3-super-120b-a12b" in ids
```

**Tavily**

```python
def test_tavily_search():
    from tavily import TavilyClient
    r = TavilyClient(api_key=os.environ["TAVILY_API_KEY"]).search(
        query="pydantic v2 field_validator migration", search_depth="advanced", max_results=3)
    assert r["results"]
```

**Sandboxes**

```python
@pytest.mark.asyncio
async def test_sandbox_run_and_fork(sandbox_service):
    base = await sandbox_service.spawn("python:3.12")
    a = await base.run(shell="echo hello > /tmp/x && cat /tmp/x")
    assert a.exit_code == 0 and "hello" in a.stdout
    # fork: the parent image must not see the child's write
    b = await base.run(shell="cat /tmp/x")
    assert b.exit_code != 0

@pytest.mark.asyncio
async def test_sandbox_clone_install_pytest(sandbox_service):
    baseline = await sandbox_service.baseline(
        "https://github.com/psf/requests", "main", "pip install -e . pytest", "pytest tests/test_structures.py -q")
    assert baseline.exit_code == 0
```

The last test is also the week-1 gate: it proves outbound network, package install, and test execution inside a sandbox.

---

## 5. Golden dataset (`tests/golden`)

### 5.1 Bug healing: 10 SWE-bench Verified instances

Chosen from the Sandboxes preloaded catalog. Selection criteria: Python, pytest, a single-file or two-file gold patch, and a fail-to-pass set of at most 10 tests. Instance IDs are listed in `tests/golden/instances.json` once selected.

For each instance the harness records: the full SSE event log, every attempt's patch and test output, token usage per model, wall-clock time, and whether fail-to-pass and pass-to-pass criteria were met. Recordings live in `tests/golden/recordings/<instance>.jsonl` and power replay mode.

Target: at least 5 of 10 resolved. Report the actual number honestly in the README and the video.

### 5.2 Migration: 2 fixtures

- `fixtures/openai_chat_service`: a small FastAPI app using `openai` chat completions with one tool call, and a pytest suite that mocks the client.
- `fixtures/anthropic_summarizer`: a script using the Anthropic Messages API with streaming, and a pytest suite that mocks the client.

Each fixture has a recorded set of 8 prompts and reference outputs. The parity harness runs the migrated code against Nemotron and reports a similarity score. The UI states that the mocked tests passing does not by itself prove behavioral parity.

### 5.3 What is deliberately not tested

- Sandbox resource limits. Nebius enforces them and does not publish the values. Testing them would test Nebius, not ARCHON.
- Network egress filtering inside sandboxes. Same reason.
- Time-to-first-token. Not under our control and not a product requirement.

---

## 6. Metrics reported per mission

| Metric | Source |
| :--- | :--- |
| Fail-to-pass tests fixed | Executor test parse on the selected attempt |
| Pass-to-pass tests broken | Same, must be 0 for `VERIFIED` |
| Iterations used | State machine |
| Tokens and cost per model | `ModelUsage` rows |
| Wall-clock time | Mission timestamps |
| Tavily queries and result counts | `tavily` events |
| Migration cost estimate | `pricing.json` with the table's last-updated date shown |

---

## 7. Running everything

```bash
cd 1.platform/server
source .venv/bin/activate

pytest tests/unit -q

NEBIUS_API_KEY=... NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/ \
NEBIUS_SANDBOX_URL=https://api.tokenfactory.nebius.com/sandboxes TAVILY_API_KEY=... \
pytest tests/integration -q

# Golden set. Uses Ultra. Records to tests/golden/recordings/.
python -m tests.golden.run --instances tests/golden/instances.json --record
```
