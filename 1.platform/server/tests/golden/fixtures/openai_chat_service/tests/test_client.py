"""Tests for chatsvc. All OpenAI traffic is faked; no network, no API key."""

import pytest

from chatsvc import client as chatsvc_client
from chatsvc.client import CLASSIFY_TOOL, DEFAULT_MODEL, classify, summarize
from conftest import FakeClient, text_response, tool_response


def test_summarize_sends_expected_request_and_returns_text():
    fake = FakeClient(text_response("  Users want dark mode.  "))

    result = summarize("A long thread about theming.", client=fake)

    assert result == "Users want dark mode."
    request = fake.last_call
    assert request["model"] == DEFAULT_MODEL
    roles = [message["role"] for message in request["messages"]]
    assert roles == ["system", "user"]
    assert request["messages"][1]["content"] == "A long thread about theming."
    assert "tools" not in request


def test_summarize_rejects_unusable_input():
    fake = FakeClient(text_response("never reached"))

    with pytest.raises(ValueError):
        summarize("   ", client=fake)
    with pytest.raises(TypeError):
        summarize(None, client=fake)

    assert fake.calls == []


def test_classify_parses_the_tool_call():
    fake = FakeClient(tool_response(label="bug", confidence=0.91))

    result = classify("The export button throws a 500.", client=fake)

    assert result == {"label": "bug", "confidence": 0.91}
    request = fake.last_call
    assert request["tools"] == [CLASSIFY_TOOL]
    assert request["tool_choice"] == "required"
    tool_name = request["tools"][0]["function"]["name"]
    assert tool_name == "record_classification"


def test_classify_rejects_malformed_tool_calls():
    unknown_label = FakeClient(tool_response(label="sandwich", confidence=1.0))
    with pytest.raises(ValueError, match="unknown label"):
        classify("hello", client=unknown_label)

    wrong_tool = FakeClient(tool_response(name="something_else", label="bug"))
    with pytest.raises(ValueError, match="unexpected tool call"):
        classify("hello", client=wrong_tool)

    no_tool = FakeClient(text_response("I refuse to use the tool."))
    with pytest.raises(ValueError, match="did not return a tool call"):
        classify("hello", client=no_tool)


def test_client_is_constructed_lazily_when_none_is_injected(monkeypatch):
    built = []

    def fake_openai(*args, **kwargs):
        built.append((args, kwargs))
        return FakeClient(text_response("Constructed on demand."))

    monkeypatch.setattr(chatsvc_client, "OpenAI", fake_openai)

    assert summarize("anything", model="gpt-5.4") == "Constructed on demand."
    assert len(built) == 1
