"""summ: blocking and streaming summarization on the Anthropic Messages API."""

from .summarizer import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    get_client,
    iter_summary,
    summarize,
    summarize_streaming,
)

__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MODEL",
    "SYSTEM_PROMPT",
    "get_client",
    "iter_summary",
    "summarize",
    "summarize_streaming",
]
__version__ = "0.1.0"
