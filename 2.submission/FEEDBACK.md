# Developer Feedback Log: Nebius Token Factory, Sandboxes, and NVIDIA Nemotron

> A product feedback section is a mandatory part of the Devpost submission and qualifies for the Most Valuable Feedback award. This file is the running log. Add an entry the moment you hit friction or find something that works unusually well. Do not try to reconstruct this in the final week.

Format per entry: date, surface, what happened, what you expected, suggestion.

---

## Token Factory inference

| Date | Observation | Expected | Suggestion |
| :--- | :--- | :--- | :--- |
| 2026-09-11 | Documentation pages for Nemotron models list display names but not the API model IDs. The IDs (`nvidia/nemotron-3-ultra-550b-a55b`, `nvidia/nemotron-3-super-120b-a12b`) only appear in one code sample and third-party catalogs. | A models table with copyable IDs, context length, and price on the Nemotron page. | Add an ID column to the Nemotron page and link to `GET /v1/models?verbose=true`. |
| 2026-09-11 | Two base URLs appear in official material: `api.tokenfactory.nebius.com/v1/` and the regional `api.tokenfactory.us-central1.nebius.com/v1/`. Unclear which to prefer and whether model availability differs. | One sentence explaining regional vs global endpoints and any tradeoffs. | Document endpoint selection in the quickstart. |

## Token Factory Sandboxes

| Date | Observation | Expected | Suggestion |
| :--- | :--- | :--- | :--- |
| 2026-09-11 | The Sandboxes overview does not state whether sandboxes have outbound network access for `git clone` and `pip install`. | An explicit statement about network egress. | Add a "networking" section to the overview. |
| 2026-09-11 | The Python SDK getting-started page never shows the `pip install` command or the import line for `Contree`. | A copy-pasteable first example. | Add install and imports to the top of the page. |
| 2026-09-11 | No published per-run CPU, memory, or wall-clock limits. Only "50 concurrent operations" and "180-day checkpoint retention". | Resource limits so agents can budget commands. | Publish the limits table. |
| 2026-09-11 | `contree-sdk` 0.3.6 differs from the docs: the constructor is `Contree(config=None, *, base_url=None, token=None)` and `IAMAuth` also requires `NEBIUS_PROJECT_ID`, which the getting-started page never mentions. `ContreeImage` has no `iter_output`, although the reference page lists it. | Docs generated from the shipped version. | Pin doc pages to SDK releases and add the project-id requirement to the first example. |
| 2026-09-11 | Fork semantics are excellent for best-of-N repair: `image.run(..., disposable=False)` gives a parent, and N children can run from it. But this is documented under "branching" with no mention of running children concurrently with `asyncio.gather`. | A short "parallel attempts" recipe. | Add a concurrency example to the branching page; it is the killer feature for SWE agents. |

## NVIDIA Nemotron models

| Date | Observation | Expected | Suggestion |
| :--- | :--- | :--- | :--- |
| | | | |

## Tavily

| Date | Observation | Expected | Suggestion |
| :--- | :--- | :--- | :--- |
| | | | |

## Things that worked well

- Sandboxes ship preloaded SWE-bench Verified environments and Git-like forking. That is exactly what a best-of-N repair agent needs and it removed a week of environment work from the plan.
