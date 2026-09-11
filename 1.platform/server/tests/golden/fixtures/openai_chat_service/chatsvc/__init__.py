"""chatsvc: summarization and classification on top of the OpenAI SDK."""

from .client import (
    CLASSIFY_TOOL,
    DEFAULT_MODEL,
    LABELS,
    classify,
    get_client,
    summarize,
)

__all__ = [
    "CLASSIFY_TOOL",
    "DEFAULT_MODEL",
    "LABELS",
    "classify",
    "get_client",
    "summarize",
]
__version__ = "0.1.0"
