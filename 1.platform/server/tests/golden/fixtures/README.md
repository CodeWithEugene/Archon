# ARCHON golden fixtures

Three small, self-contained Python projects used as test targets by the
autonomous repair agent. Each directory is its own standalone git repository
(single commit, branch `main`) because the agent clones it before working on it.

Every fixture exposes the same two entry points:

| Script | Meaning |
| --- | --- |
| `./install.sh` | `pip install -e . pytest` into the active interpreter |
| `./test.sh` | `pytest -q` |

Both honour a `PYTHON` environment variable so a fixture can be driven against
an arbitrary interpreter without activating a virtualenv:

```bash
PYTHON=/path/to/venv/bin/python ./install.sh
PYTHON=/path/to/venv/bin/python ./test.sh
```

Fixtures 2 and 3 make no network calls and need no API key: the provider SDK
client is faked in `tests/conftest.py`.

---

## 1. `broken_pydantic_v2/` — bug-healing target (baseline: **FAIL**)

A pure-Python package `userkit/` whose schema layer is written against the
Pydantic V1 API while `pyproject.toml` pins `pydantic>=2,<3`.

```bash
cd broken_pydantic_v2
./install.sh
./test.sh
```

**Expected baseline:** `4 failed, 2 passed`

Failing tests:

- `tests/test_schemas.py::test_user_to_dict_uses_v2_serialization`
- `tests/test_schemas.py::test_parse_user_uses_v2_validation`
- `tests/test_schemas.py::test_user_from_row_reads_attributes`
- `tests/test_schemas.py::test_model_declares_v2_config_and_validators`

Passing tests (a valid repair must keep these green):

- `tests/test_schemas.py::test_email_is_normalized`
- `tests/test_schemas.py::test_invalid_email_is_rejected`

**Repair target:** `@validator` to `@field_validator`, `class Config:
orm_mode = True` to `model_config = ConfigDict(from_attributes=True)`,
`.dict()` to `.model_dump()`, and `.parse_obj()` / `.from_orm()` to
`.model_validate()`. `EXPECTED_FIX.md` describes the change; `solution.patch`
is a reference fix that applies cleanly to a clean checkout:

```bash
git apply solution.patch && ./test.sh   # -> 6 passed
```

Note that only `from_orm` raises outright under Pydantic 2; the other three
call sites emit `PydanticDeprecatedSince20`, which the tests promote to errors
via `warnings.simplefilter("error", DeprecationWarning)`.

---

## 2. `openai_chat_service/` — migration target (baseline: **PASS**)

A package `chatsvc/` calling `client.chat.completions.create(...)` on the
OpenAI SDK (v2+ client API, `openai>=2`). `summarize(text)` returns a one
sentence summary; `classify(text)` sends a single function/tool definition and
parses the resulting `tool_calls` entry.

```bash
cd openai_chat_service
./install.sh
./test.sh
```

**Expected baseline:** `5 passed`

`parity_prompts.json` holds 8 hand-written entries
(`{id, function, input, reference_output}`, four per function) for comparing
pre- and post-migration behaviour.

---

## 3. `anthropic_summarizer/` — migration target (baseline: **PASS**)

A package `summ/` calling the Anthropic Messages API. `summarize(text)` uses
`client.messages.create(...)` with a `system` prompt and structured content
blocks; `summarize_streaming(text)` uses `client.messages.stream(...)` as a
context manager and iterates `text_stream`. `iter_summary(text)` exposes the
raw chunk generator.

```bash
cd anthropic_summarizer
./install.sh
./test.sh
```

**Expected baseline:** `4 passed`

`parity_prompts.json` holds 8 hand-written entries
(`{id, function, input, reference_output}`, four per function).

---

## Verified baselines

Recorded against Python 3.12 in isolated virtualenvs:

| Fixture | Result | pytest summary |
| --- | --- | --- |
| `broken_pydantic_v2` | fail (expected) | `4 failed, 2 passed, 4 warnings` |
| `broken_pydantic_v2` + `solution.patch` | pass | `6 passed` |
| `openai_chat_service` | pass | `5 passed` |
| `anthropic_summarizer` | pass | `4 passed` |

Pinned versions at verification time: `pydantic 2.13.5`, `openai 3.13.0`,
`anthropic 1.5.0`, `pytest 9.1.1`.

The fixture list is also machine-readable in `../instances.json`.
