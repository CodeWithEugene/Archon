"""Tracing helpers must be no-ops without a key and must scrub what they send when enabled."""

from __future__ import annotations

import os

import pytest

from app.core.models import TestReport
from app.observability import tracing


@pytest.fixture(autouse=True)
def _reset_env() -> None:  # type: ignore[misc]
    saved = {
        k: os.environ.get(k)
        for k in ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT", "LANGSMITH_ENDPOINT")
    }
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_disabled_without_key() -> None:
    assert tracing.configure("") is False
    assert not tracing.enabled()
    assert tracing.current_trace_url() is None
    tracing.annotate(metadata={"x": 1})  # must not raise


def test_enabled_with_key_sets_env() -> None:
    assert tracing.configure("lsv2_pt_fake", project="archon-test", endpoint="http://127.0.0.1:9") is True
    assert tracing.enabled()
    assert os.environ["LANGSMITH_PROJECT"] == "archon-test"
    os.environ["LANGSMITH_TRACING"] = "false"


async def test_traced_function_still_works_when_disabled() -> None:
    os.environ["LANGSMITH_TRACING"] = "false"

    @tracing.traced("unit.add", run_type="tool")
    async def add(a: int, b: int) -> int:
        return a + b

    assert await add(2, 3) == 5


def test_scrub_drops_self_and_caps_strings() -> None:
    class Svc:
        pass

    Svc.__module__ = "app.fake"
    big = "x" * 10_000
    out = tracing.scrub({"self": Svc(), "on_output": lambda: None, "text": big, "svc": Svc(), "b": b"12", "n": 3})
    assert "self" not in out and "on_output" not in out
    assert out["text"].startswith("x" * 100) and "more chars" in out["text"]
    assert out["svc"] == "<Svc>" and out["b"] == "<2 bytes>" and out["n"] == 3


def test_scrub_expands_models_and_dataclasses() -> None:
    report = TestReport(exit_code=1, failed=["t::a"], passed=["t::b"])
    out = tracing.scrub({"report": report})
    assert out["report"]["failed"] == ["t::a"] and out["report"]["exit_code"] == 1


def test_wrap_openai_client_is_identity_when_disabled() -> None:
    os.environ["LANGSMITH_TRACING"] = "false"
    sentinel = object()
    assert tracing.wrap_openai_client(sentinel) is sentinel
