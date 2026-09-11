"""Summarization helpers built on the Anthropic Messages API.

Every public function accepts an optional ``client`` so callers (and tests) can
inject a stand-in. When omitted, a real :class:`anthropic.Anthropic` client is
built from the ambient environment.
"""

from typing import Any, Iterator, List, Optional

from anthropic import Anthropic

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 512

SYSTEM_PROMPT = (
    "You are a precise summarizer. Reply with two sentences at most and do "
    "not add a preamble, a heading, or a closing remark."
)


def get_client() -> Anthropic:
    """Build an Anthropic client from the ambient environment."""
    return Anthropic()


def _require_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("text must not be empty")
    return cleaned


def _user_messages(text: str) -> List[dict]:
    return [{"role": "user", "content": [{"type": "text", "text": text}]}]


def _request(text: str, model: str, max_tokens: int) -> dict:
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT,
        "messages": _user_messages(text),
    }


def _extract_text(message: Any) -> str:
    """Join every text block of a Messages API response."""
    blocks = getattr(message, "content", None)
    if not blocks:
        raise ValueError("model returned an empty message")
    parts = [
        block.text
        for block in blocks
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ]
    if not parts:
        raise ValueError("model returned no text blocks")
    return "".join(parts).strip()


def summarize(
    text: str,
    *,
    client: Optional[Anthropic] = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Summarize ``text`` in a single blocking call."""
    cleaned = _require_text(text)
    client = client or get_client()
    message = client.messages.create(**_request(cleaned, model, max_tokens))
    return _extract_text(message)


def iter_summary(
    text: str,
    *,
    client: Optional[Anthropic] = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Iterator[str]:
    """Yield summary fragments as the model produces them."""
    cleaned = _require_text(text)
    client = client or get_client()
    with client.messages.stream(**_request(cleaned, model, max_tokens)) as stream:
        for chunk in stream.text_stream:
            if chunk:
                yield chunk


def summarize_streaming(
    text: str,
    *,
    client: Optional[Anthropic] = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Stream a summary and return the assembled text."""
    parts = list(iter_summary(text, client=client, model=model, max_tokens=max_tokens))
    if not parts:
        raise ValueError("stream produced no text")
    return "".join(parts).strip()
