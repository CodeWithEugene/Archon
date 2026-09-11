"""Offline test doubles for the Anthropic client.

Nothing here touches the network and no ANTHROPIC_API_KEY is required.
"""

from types import SimpleNamespace

import pytest


def text_message(*texts):
    """Build a Messages API response made of text blocks."""
    blocks = [SimpleNamespace(type="text", text=t) for t in texts]
    return SimpleNamespace(
        id="msg_0",
        role="assistant",
        content=blocks,
        stop_reason="end_turn",
    )


class FakeStream:
    """Context manager mimicking ``client.messages.stream(...)``."""

    def __init__(self, chunks):
        self.text_stream = iter(chunks)
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited = True
        return False


class FakeMessages:
    def __init__(self, responses, chunks):
        self._responses = list(responses)
        self._chunks = list(chunks)
        self.calls = []
        self.stream_calls = []
        self.streams = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeClient ran out of scripted responses")
        return self._responses.pop(0)

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        stream = FakeStream(self._chunks)
        self.streams.append(stream)
        return stream


class FakeClient:
    """Stands in for :class:`anthropic.Anthropic`."""

    def __init__(self, *responses, chunks=()):
        self.messages = FakeMessages(responses, chunks)

    @property
    def last_call(self):
        assert self.messages.calls, "no blocking request was made"
        return self.messages.calls[-1]

    @property
    def last_stream_call(self):
        assert self.messages.stream_calls, "no streaming request was made"
        return self.messages.stream_calls[-1]


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    """Guarantee the suite cannot accidentally authenticate."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
