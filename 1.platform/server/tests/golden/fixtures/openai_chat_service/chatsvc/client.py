"""Chat helpers built on the OpenAI SDK (v2+ client API).

Both public functions accept an optional ``client`` so callers (and tests) can
inject a stand-in. When omitted, a real :class:`openai.OpenAI` client is built
from the ambient environment.
"""

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

DEFAULT_MODEL = "gpt-5.4"

LABELS = ("bug", "feature_request", "question", "praise", "other")

SUMMARY_SYSTEM_PROMPT = "You are a terse summarizer. Reply with a single sentence, no preamble."

CLASSIFY_SYSTEM_PROMPT = (
    "You label inbound user messages. Always call the record_classification tool exactly once."
)

CLASSIFY_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "record_classification",
        "description": "Record the label for a single inbound message.",
        "parameters": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "enum": list(LABELS),
                    "description": "The category the message belongs to.",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence in the label, between 0 and 1.",
                },
            },
            "required": ["label", "confidence"],
            "additionalProperties": False,
        },
    },
}


def get_client() -> OpenAI:
    """Build an OpenAI client from the ambient environment."""
    return OpenAI()


def _messages(system: str, text: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]


def _require_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("text must not be empty")
    return cleaned


def summarize(
    text: str,
    *,
    client: Optional[OpenAI] = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Summarize ``text`` into a single sentence."""
    cleaned = _require_text(text)
    client = client or get_client()
    response = client.chat.completions.create(
        model=model,
        messages=_messages(SUMMARY_SYSTEM_PROMPT, cleaned),
    )
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("model returned no content for summarize()")
    return content.strip()


def classify(
    text: str,
    *,
    client: Optional[OpenAI] = None,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """Classify ``text`` into one of :data:`LABELS` via a tool call."""
    cleaned = _require_text(text)
    client = client or get_client()
    response = client.chat.completions.create(
        model=model,
        messages=_messages(CLASSIFY_SYSTEM_PROMPT, cleaned),
        tools=[CLASSIFY_TOOL],
        tool_choice="required",
    )
    return _parse_tool_call(response)


def _parse_tool_call(response: Any) -> Dict[str, Any]:
    """Pull the first ``record_classification`` call out of a response."""
    tool_calls = getattr(response.choices[0].message, "tool_calls", None)
    if not tool_calls:
        raise ValueError("model did not return a tool call")
    call = tool_calls[0]
    if call.function.name != "record_classification":
        raise ValueError(f"unexpected tool call: {call.function.name}")
    try:
        payload = json.loads(call.function.arguments)
    except json.JSONDecodeError as exc:
        raise ValueError("tool call arguments were not valid JSON") from exc
    label = payload.get("label")
    if label not in LABELS:
        raise ValueError(f"unknown label: {label!r}")
    return {"label": label, "confidence": float(payload.get("confidence", 0.0))}
