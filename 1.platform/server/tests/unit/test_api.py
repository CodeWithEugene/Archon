"""HTTP-level tests: create, stream, inspect, auth, replay, health."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.main import create_app
from app.sandbox.fake import FakeBackend
from app.settings import Settings
from tests.unit.conftest import ALL_PASS, SERVER_ROOT


def _settings(tmp_path: Path, **over: object) -> Settings:
    base = dict(
        NEBIUS_API_KEY="",
        ARCHON_LLM_BACKEND="fake",
        ARCHON_SANDBOX_BACKEND="fake",
        ARCHON_DB_PATH=tmp_path / "api.db",
        ARCHON_RECORDINGS_DIR=tmp_path / "rec",
        ARCHON_PRICING_PATH=SERVER_ROOT / "pricing.json",
        ARCHON_SWE_INSTANCES=tmp_path / "none.json",
        ARCHON_ENV="development",
    )
    base.update(over)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg, arg-type]


@pytest.fixture
async def client_and_backend(tmp_path: Path) -> AsyncIterator[tuple[httpx.AsyncClient, FakeBackend]]:
    backend = FakeBackend(default_files={"/work/repo/pyproject.toml": b"[project]"})
    backend.on(r"git clone", stdout="ok")
    backend.on(r"pytest", stdout=ALL_PASS, exit_code=0)
    app = create_app(_settings(tmp_path), backend=backend)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c, backend


async def _read_until_done(client: httpx.AsyncClient, url: str, wait_s: float = 5.0) -> list[tuple[str, dict]]:  # type: ignore[type-arg]
    events: list[tuple[str, dict]] = []  # type: ignore[type-arg]

    async def go() -> None:
        async with client.stream("GET", url) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            kind = ""
            async for line in resp.aiter_lines():
                if line.startswith("event: "):
                    kind = line[7:]
                elif line.startswith("data: "):
                    events.append((kind, json.loads(line[6:])))
                    if kind == "done":
                        return

    await asyncio.wait_for(go(), timeout=wait_s)
    return events


async def _wait_for_replays(client: httpx.AsyncClient, wait_s: float = 3.0) -> list[dict]:  # type: ignore[type-arg]
    deadline = asyncio.get_running_loop().time() + wait_s
    while True:
        reps: list[dict] = (await client.get("/api/v1/replays")).json()  # type: ignore[type-arg]
        if reps or asyncio.get_running_loop().time() > deadline:
            return reps
        await asyncio.sleep(0.05)


async def test_health(client_and_backend) -> None:  # type: ignore[no-untyped-def]
    client, _ = client_and_backend
    r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["sandbox_backend"] == "fake" and body["models"]["ultra"].startswith("nvidia/")


async def test_create_stream_and_inspect(client_and_backend) -> None:  # type: ignore[no-untyped-def]
    client, _ = client_and_backend
    r = await client.post(
        "/api/v1/missions",
        json={"type": "BUG_HEALING", "repo_url": "https://github.com/acme/demo", "test_command": "pytest -q"},
    )
    assert r.status_code == 202, r.text
    mid = r.json()["id"]
    events = await _read_until_done(client, r.json()["stream"])
    kinds = [k for k, _ in events]
    assert kinds[0] == "status" and kinds[-1] == "done"
    assert events[-1][1]["status"] == "NOTHING_TO_FIX"
    assert any(k == "terminal" and d["attempt"] == "baseline" for k, d in events)

    detail = await client.get(f"/api/v1/missions/{mid}")
    assert detail.status_code == 200 and detail.json()["status"] == "NOTHING_TO_FIX"
    assert (await client.get(f"/api/v1/missions/{mid}/diff")).json() == []
    assert (await client.get(f"/api/v1/missions/{mid}/patch")).status_code == 404
    # Replaying the stream after completion comes from the store and still ends with done.
    again = await _read_until_done(client, f"/api/v1/missions/{mid}/events")
    assert again[-1][0] == "done"
    # Last-Event-ID resumes
    async with client.stream(
        "GET", f"/api/v1/missions/{mid}/events", headers={"Last-Event-ID": str(len(again) - 1)}
    ) as resp:
        lines = [ln async for ln in resp.aiter_lines() if ln.startswith("event: ")]
    assert lines == ["event: done"]
    # Recorded because env=development
    reps = await _wait_for_replays(client)
    assert reps and reps[0]["id"] == mid


async def test_validation_errors(client_and_backend) -> None:  # type: ignore[no-untyped-def]
    client, _ = client_and_backend
    bad = await client.post(
        "/api/v1/missions", json={"type": "BUG_HEALING", "repo_url": "file:///tmp/x", "test_command": "pytest"}
    )
    assert bad.status_code == 422
    bad2 = await client.post("/api/v1/missions", json={"type": "BUG_HEALING", "swe_instance_id": "nope"})
    assert bad2.status_code == 422
    assert (await client.get("/api/v1/missions/m_missing")).status_code == 404
    assert (await client.get("/api/v1/missions/m_missing/events")).status_code == 404


async def test_live_mode_requires_token(tmp_path: Path) -> None:
    backend = FakeBackend()
    backend.on(r"pytest", stdout=ALL_PASS)
    app = create_app(_settings(tmp_path, ARCHON_DEMO_TOKEN="s3cret"), backend=backend)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            body = {"type": "BUG_HEALING", "repo_url": "https://github.com/acme/demo", "test_command": "pytest"}
            assert (await client.post("/api/v1/missions", json=body)).status_code == 401
            assert (
                await client.post("/api/v1/missions", json=body, headers={"Authorization": "Bearer wrong"})
            ).status_code == 401
            ok = await client.post("/api/v1/missions", json=body, headers={"Authorization": "Bearer s3cret"})
            assert ok.status_code == 202
            # replays never need the token
            await _read_until_done(client, ok.json()["stream"])
            reps = await _wait_for_replays(client)
            play = await client.post(f"/api/v1/replays/{reps[0]['id']}/play?speed=8")
            assert play.status_code == 202 and play.json()["id"].startswith("rp_")
            replayed = await _read_until_done(client, play.json()["stream"], wait_s=15)
            assert replayed[-1][0] == "done" and replayed[-1][1]["status"] == "NOTHING_TO_FIX"


async def test_pricing_endpoints(client_and_backend) -> None:  # type: ignore[no-untyped-def]
    client, _ = client_and_backend
    p = await client.get("/api/v1/pricing")
    assert p.status_code == 200 and "nvidia/nemotron-3-ultra-550b-a55b" in p.json()["models"]
    e = await client.get("/api/v1/pricing/estimate", params={"source_model": "claude-sonnet-5"})
    assert e.status_code == 200 and e.json()["target_model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert (await client.get("/api/v1/pricing/estimate", params={"source_model": "nope"})).status_code == 404
