"""Live integration tests. Each is skipped unless its key is present. They spend a few cents."""

from __future__ import annotations

import os

import pytest

NEBIUS = os.getenv("NEBIUS_API_KEY")
TAVILY = os.getenv("TAVILY_API_KEY")
PROJECT = os.getenv("NEBIUS_PROJECT_ID")
BASE = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
SBX = os.getenv("NEBIUS_SANDBOX_URL", "https://api.tokenfactory.nebius.com/sandboxes/")


@pytest.mark.skipif(not NEBIUS, reason="NEBIUS_API_KEY not set")
async def test_models_endpoint_lists_nemotron() -> None:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=NEBIUS, base_url=BASE)
    ids = {m.id for m in (await client.models.list()).data}
    assert "nvidia/nemotron-3-super-120b-a12b" in ids, sorted(i for i in ids if "nemotron" in i)
    assert "nvidia/nemotron-3-ultra-550b-a55b" in ids, sorted(i for i in ids if "nemotron" in i)
    nano = sorted(i for i in ids if "nemotron-3-nano" in i)
    assert nano, "no Nemotron 3 Nano id found; update ARCHON_NANO_MODEL"
    print("NANO IDS:", nano)


@pytest.mark.skipif(not NEBIUS, reason="NEBIUS_API_KEY not set")
async def test_super_completion_and_json_mode() -> None:
    from app.core.pricing import PriceTable
    from app.core.router import ModelRouter, Task
    from app.llm.client import NebiusLLM
    from app.settings import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    llm = NebiusLLM(api_key=NEBIUS or "", base_url=BASE, router=ModelRouter(s), prices=PriceTable.load(s.pricing_path))
    comp = await llm.complete(Task.REVIEW, [{"role": "user", "content": "Reply with exactly: PING_OK"}], max_tokens=16)
    assert "PING_OK" in comp.text
    obj, comp2 = await llm.complete_json(
        Task.RESEARCH_QUERIES, [{"role": "user", "content": 'Return {"queries": ["a", "b"]} exactly.'}], max_tokens=60
    )
    assert obj.get("queries") == ["a", "b"]
    assert comp2.prompt_tokens > 0 and comp2.cost_usd >= 0


@pytest.mark.skipif(not TAVILY, reason="TAVILY_API_KEY not set")
async def test_tavily_search() -> None:
    from app.grounding.tavily import TavilyGrounder

    g = TavilyGrounder(api_key=TAVILY or "", timeout_s=15)
    r = await g.search("pydantic v2 field_validator replaces validator")
    assert r.error is None and r.hits, r
    r2 = await g.search("pydantic v2 field_validator replaces validator")
    assert r2.cached


@pytest.mark.skipif(not (NEBIUS and PROJECT), reason="NEBIUS_API_KEY and NEBIUS_PROJECT_ID not set")
async def test_sandbox_run_fork_and_clone() -> None:
    """Week-1 gate: outbound network, package install, and test execution inside a Sandbox."""
    from app.sandbox.base import RunSpec
    from app.sandbox.contree import ContreeBackend
    from app.sandbox.service import SandboxService

    be = ContreeBackend(token=NEBIUS or "", base_url=SBX, project_id=PROJECT or "")
    base = await be.base_image("python:3.12-slim")
    a = await be.run(base, RunSpec(shell="echo hello > /tmp/x && cat /tmp/x", timeout_s=120))
    assert a.exit_code == 0 and "hello" in a.stdout and a.image_id
    b = await be.run(base, RunSpec(shell="cat /tmp/x", timeout_s=120))
    assert b.exit_code != 0, "fork isolation broken: sibling saw parent's write"
    svc = SandboxService(be, base_image_ref="python:3.12-slim", command_timeout_s=900)
    image = await svc.provision_repo(
        "https://github.com/psf/requests",
        "main",
        "apt-get update -qq && apt-get install -y -qq git >/dev/null; python -m pip install -q -e . pytest",
        None,
    )
    res, report = await svc.run_tests(image, "pytest tests/test_structures.py -q", None)
    assert report.exit_code == 0, res.combined[-2000:]
    await be.close()
