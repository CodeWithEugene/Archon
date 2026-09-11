"""Offline test doubles for the OpenAI client.

Nothing here touches the network and no OPENAI_API_KEY is required.
"""

import json
from types import SimpleNamespace

import pytest


def text_response(content):
    """Build a chat completion that carries plain text."""
    message = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_response(name="record_classification", **arguments):
    """Build a chat completion that carries a single tool call."""
    call = SimpleNamespace(
        id="call_0",
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )
    message = SimpleNamespace(content=None, tool_calls=[call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeClient ran out of scripted responses")
        return self._responses.pop(0)


class FakeClient:
    """Stands in for :class:`openai.OpenAI`."""

    def __init__(self, *responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))

    @property
    def calls(self):
        return self.chat.completions.calls

    @property
    def last_call(self):
        assert self.calls, "no request was made"
        return self.calls[-1]


@pytest.fixture
def fake_client_factory():
    return FakeClient


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    """Guarantee the suite cannot accidentally authenticate."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
