# Developer Feedback Log: Nebius Token Factory, Sandboxes, and NVIDIA Nemotron

> A product feedback section is a mandatory part of the Devpost submission and qualifies for the Most Valuable Feedback award. This file is the running log. Add an entry the moment you hit friction or find something that works unusually well. Do not try to reconstruct this in the final week.

Format per entry: date, surface, what happened, what you expected, suggestion.

---

## Token Factory inference

| Date | Observation | Expected | Suggestion |
| :--- | :--- | :--- | :--- |
| 2026-09-11 | Documentation pages for Nemotron models list display names but not the API model IDs. The IDs (`nvidia/Nemotron-3-Ultra-550b-a55b`, `nvidia/nemotron-3-super-120b-a12b`) only appear in one code sample and third-party catalogs. | A models table with copyable IDs, context length, and price on the Nemotron page. | Add an ID column to the Nemotron page and link to `GET /v1/models?verbose=true`. |
| 2026-09-11 | Two base URLs appear in official material: `api.tokenfactory.nebius.com/v1/` and the regional `api.tokenfactory.us-central1.nebius.com/v1/`. Unclear which to prefer and whether model availability differs. | One sentence explaining regional vs global endpoints and any tradeoffs. | Document endpoint selection in the quickstart. |

| 2026-09-12 | Nemotron model IDs on Token Factory have inconsistent casing: `nvidia/Nemotron-3-Ultra-550b-a55b`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`. Every public catalog and blog post lowercases them, so copy-pasted IDs 404. | Consistent lowercase IDs, or case-insensitive matching on the API. | Normalize IDs or accept case-insensitive model names. |
| 2026-09-12 | Nemotron 3 thinks by default and reasoning tokens count against `max_tokens`. A 16-token request returns `content=""` with `finish_reason=length` and the answer only in `reasoning_content`. `chat_template_kwargs.enable_thinking=false` fixes it but is not mentioned in the Token Factory docs. | Documentation of thinking control and the `reasoning_content` field on the Nemotron page. | Add a "reasoning models" section with the `enable_thinking` switch and budget guidance. |
| 2026-09-12 | `GET /v1/models?verbose=true` is excellent: it returns IDs, context length, and per-token prices. It is the only place I found the real prices. | Link to it from the pricing page. | Surface the verbose models endpoint prominently. |

## Token Factory Sandboxes

| Date | Observation | Expected | Suggestion |
| :--- | :--- | :--- | :--- |
| 2026-09-11 | The Sandboxes overview does not state whether sandboxes have outbound network access for `git clone` and `pip install`. | An explicit statement about network egress. | Add a "networking" section to the overview. |
| 2026-09-11 | The Python SDK getting-started page never shows the `pip install` command or the import line for `Contree`. | A copy-pasteable first example. | Add install and imports to the top of the page. |
| 2026-09-11 | No published per-run CPU, memory, or wall-clock limits. Only "50 concurrent operations" and "180-day checkpoint retention". | Resource limits so agents can budget commands. | Publish the limits table. |
| 2026-09-11 | `contree-sdk` 0.3.6 differs from the docs: the constructor is `Contree(config=None, *, base_url=None, token=None)` and `IAMAuth` also requires `NEBIUS_PROJECT_ID`, which the getting-started page never mentions. `ContreeImage` has no `iter_output`, although the reference page lists it. | Docs generated from the shipped version. | Pin doc pages to SDK releases and add the project-id requirement to the first example. |
| 2026-09-11 | Fork semantics are excellent for best-of-N repair: `image.run(..., disposable=False)` gives a parent, and N children can run from it. But this is documented under "branching" with no mention of running children concurrently with `asyncio.gather`. | A short "parallel attempts" recipe. | Add a concurrency example to the branching page; it is the killer feature for SWE agents. |

| 2026-09-12 | With a freshly issued key, `whoami` on the Sandboxes API succeeds but every permission (`spawn`, `import`, `list`, `cancel`, `set_image_tag`) is `false`, and every operation returns a bare "You do not have permission to perform this action". Nothing in the console or the error says how to get access. | A 403 body that says "Sandboxes beta access is not enabled for project X; request it at ...". | Link the access request from the error and from the console. |
| 2026-09-12 | The Sandboxes `whoami` endpoint reports `token_expiration` a few minutes ahead even for a long-lived console API key, and the SDK logs "Token expires in 0 hours" on every client construction. The value appears to be a derived session token's expiry, not the key's. It caused a false alarm. | `token_expiration` to describe the credential I supplied, or a field name that says what it is. | Rename or document the field and drop the SDK warning when the auth type is an API key. |
| 2026-09-12 | Sandboxes worked first time once permissions were granted: spawn from `python:3.12-slim`, fork isolation, outbound network for `apt-get` and `git clone`, `pip install -e .`, pytest inside the VM. The full gate took about 30 seconds. | | Nothing to fix. This is the best part of the platform. |
| 2026-09-12 | The Sandboxes run shell is `/bin/sh`. In the SWE-bench images `source /opt/miniconda3/bin/activate` fails silently and `conda activate` never happens, so `pytest` is not found. Nothing documents the shell. | The docs to state the shell, and a `shell=` option or a bash default when bash is present. | Document the default shell on the SDK `run()` page; consider running via bash when available. |
| 2026-09-12 | The preloaded SWE-bench Verified images are excellent: `swebench/sweb.eval.x86_64.<owner>_1776_<repo>-<n>:latest` resolves by tag with `images.use(tag, strict=True)`, boots in seconds, and has the repo at `/testbed` with the `testbed` conda env. The tag convention and the `/testbed` layout are not documented anywhere I could find. | A page listing the tag pattern, the repo path, the env name, and how to apply the instance test patch. | Add a "using the SWE-bench catalog" page with one worked example. |
| 2026-09-12 | `python:3.12-slim` has no `git`, so every SWE-style workflow must `apt-get install git` first. | A documented "recommended base images for code agents" list, or a Nebius-published image with git, build tools, and common runtimes. | Publish `nebius/agent-python:3.12` or similar. |

| 2026-09-12 | Not a Nebius bug, but worth knowing for anyone using the preloaded SWE-bench Verified images: the upstream dataset stores some parametrized test ids truncated at the first space (`psf__requests-5414`: `test_basic_auth_str_is_always_native[test-test-Basic`). Passing them to pytest aborts the whole run with exit 4. | A note on the SWE agents page. | Mention the id quirk and suggest running test files or prefix-matching ids. |

## NVIDIA Nemotron models

| Date | Observation | Expected | Suggestion |
| :--- | :--- | :--- | :--- |
| 2026-09-12 | Nemotron 3 Ultra's diagnoses were correct on every live run, and with search-and-replace edits its fixes applied first time. Its hand-written unified diffs never applied (five of five). | Guidance in the model card that agents should use edit blocks, not diffs. | Add an "agentic editing" recommendation to the Nemotron 3 docs. |
| 2026-09-12 | Ultra sometimes drops required top-level JSON keys (`root_cause`) or emits tool-call shaped JSON (`{"tool": "read", ...}`) when asked for a schema, even with `response_format=json_object`. Super and Nano followed the schema reliably. | Structured outputs with a JSON schema on Token Factory for Nemotron 3 Ultra. | Support `response_format={"type": "json_schema", ...}` server-side. |
| 2026-09-12 | In long prompts (a monorepo subproject with the test file, two sources, and a file list), Ultra paraphrased the source instead of copying it: search blocks referenced a `UserCreate` class and a `name` field that do not exist, on four separate runs, even after the real text was quoted back. On the same files as a standalone repository it copied correctly first try. | Better long-context faithfulness, or a documented recommendation to keep edit prompts short and put sources last. | Publish prompt-shape guidance for edit-style agent tasks. |
| 2026-09-12 | Thinking on by default with reasoning tokens counted against `max_tokens` is easy to trip over; `chat_template_kwargs.enable_thinking=false` fixes it and should be documented. | | See the Token Factory note above. |

## Tavily

| Date | Observation | Expected | Suggestion |
| :--- | :--- | :--- | :--- |
| 2026-09-12 | Search quality for stack-trace style queries is good: three queries synthesized from a Pydantic deprecation failure returned the official migration guide first. Latency 0.2 to 4 s per `advanced` search. | | Nothing to fix. |
| 2026-09-12 | The `tavily-python` async client has no per-request timeout parameter; I wrap it in `asyncio.wait_for`. | A `timeout=` argument on `search()`. | Add a timeout parameter. |

## Things that worked well

- Sandboxes ship preloaded SWE-bench Verified environments and Git-like forking. That is exactly what a best-of-N repair agent needs and it removed a week of environment work from the plan.
