"""Tests for summ. All Anthropic traffic is faked; no network, no API key."""

import pytest

from conftest import FakeClient, text_message
from summ import summarizer as summ_summarizer
from summ.summarizer import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    summarize,
    summarize_streaming,
)


def test_summarize_sends_expected_request_and_returns_text():
    fake = FakeClient(text_message("  The registry timed out.  "))

    result = summarize("A long incident write-up.", client=fake)

    assert result == "The registry timed out."
    request = fake.last_call
    assert request["model"] == DEFAULT_MODEL
    assert request["max_tokens"] == DEFAULT_MAX_TOKENS
    assert request["system"] == SYSTEM_PROMPT
    assert request["messages"] == [
        {
            "role": "user",
            "content": [{"type": "text", "text": "A long incident write-up."}],
        }
    ]


def test_summarize_validates_input_and_response():
    fake = FakeClient(text_message("never reached"))
    with pytest.raises(ValueError):
        summarize("   ", client=fake)
    with pytest.raises(TypeError):
        summarize(None, client=fake)
    assert fake.messages.calls == []

    empty = FakeClient(text_message())
    with pytest.raises(ValueError, match="empty message"):
        summarize("hello", client=empty)


def test_summarize_streaming_joins_chunks_from_the_context_manager():
    fake = FakeClient(chunks=["Retention ", "rose ", "to 91 percent. "])

    result = summarize_streaming("Quarterly retention notes.", client=fake)

    assert result == "Retention rose to 91 percent."
    stream = fake.messages.streams[0]
    assert stream.entered and stream.exited, "stream must be used as a context manager"
    request = fake.last_stream_call
    assert request["model"] == DEFAULT_MODEL
    assert request["system"] == SYSTEM_PROMPT
    assert request["messages"][0]["content"][0]["text"] == "Quarterly retention notes."
    assert fake.messages.calls == [], "streaming must not call messages.create"


def test_client_is_constructed_lazily_when_none_is_injected(monkeypatch):
    built = []

    def fake_anthropic(*args, **kwargs):
        built.append((args, kwargs))
        return FakeClient(text_message("Constructed on demand."))

    monkeypatch.setattr(summ_summarizer, "Anthropic", fake_anthropic)

    assert summarize("anything") == "Constructed on demand."
    assert len(built) == 1
