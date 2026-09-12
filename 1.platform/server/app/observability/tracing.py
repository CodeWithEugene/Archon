"""LangSmith tracing. Enabled only when LANGSMITH_API_KEY is set; otherwise every helper is a no-op.

Trace shape per mission:
  archon.mission (chain)                      root, tagged with mission type, metadata mission_id
    sandbox.provision / sandbox.baseline (tool)
    researcher.research (chain)
      tavily.search (retriever)               one per query
      nemotron chat.completions (llm)         via wrap_openai on the Nebius client
    engineer.propose (chain)
      nemotron chat.completions (llm)
    sandbox.try_patch (tool)                  one per candidate, run concurrently
    reviewer.review (chain)
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any, TypeVar, cast

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])
DEFAULT_PROJECT = "archon"


def configure(api_key: str, project: str = DEFAULT_PROJECT, endpoint: str | None = None) -> bool:
    """Turn tracing on for this process. Returns True when enabled.

    The langsmith SDK reads its configuration from environment variables, so this sets them once at startup
    from our typed settings instead of requiring operators to know the SDK's variable names.
    """
    if not api_key:
        os.environ["LANGSMITH_TRACING"] = "false"
        return False
    os.environ["LANGSMITH_API_KEY"] = api_key
    os.environ["LANGSMITH_PROJECT"] = project
    os.environ["LANGSMITH_TRACING"] = "true"
    if endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = endpoint
    try:
        import langsmith  # noqa: F401
    except ImportError:
        logger.warning("LANGSMITH_API_KEY set but the langsmith package is missing; tracing disabled")
        os.environ["LANGSMITH_TRACING"] = "false"
        return False
    logger.info("LangSmith tracing enabled, project=%s", project)
    return True


def enabled() -> bool:
    return os.environ.get("LANGSMITH_TRACING", "").lower() in {"true", "1", "yes"}


MAX_STR = 6000
DROP_KEYS = {"self", "on_output", "on_search", "hook"}


def scrub(value: Any, depth: int = 0) -> Any:
    """Make a value safe and small for a trace: drop callables and `self`, cap strings, expand models."""
    if depth > 6:
        return "<depth>"
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return value if len(value) <= MAX_STR else value[:MAX_STR] + f"... [{len(value) - MAX_STR} more chars]"
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if callable(value) and not hasattr(value, "model_dump"):
        return "<callable>"
    if isinstance(value, dict):
        return {str(k): scrub(v, depth + 1) for k, v in value.items() if str(k) not in DROP_KEYS}
    if isinstance(value, list | tuple | set):
        items = list(value)
        out = [scrub(v, depth + 1) for v in items[:50]]
        if len(items) > 50:
            out.append(f"<{len(items) - 50} more items>")
        return out
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return scrub(dump(mode="json"), depth + 1)
        except Exception:  # noqa: BLE001
            return repr(value)[:MAX_STR]
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import fields

        return {f.name: scrub(getattr(value, f.name), depth + 1) for f in fields(value) if not f.name.startswith("_")}
    if hasattr(value, "__dict__") and type(value).__module__.startswith("app."):
        # Domain objects (runner, services): identify, do not serialize.
        return f"<{type(value).__name__}>"
    return repr(value)[:MAX_STR]


def _scrub_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return {k: scrub(v) for k, v in inputs.items() if k not in DROP_KEYS}


def _scrub_outputs(outputs: Any) -> Any:
    return scrub(outputs)


def traced(name: str, run_type: str = "chain", **kwargs: Any) -> Callable[[F], F]:
    """Decorator: `@traced("engineer.propose")`. Cheap when tracing is off; langsmith checks at call time.

    Inputs and outputs are scrubbed by default so `self`, callbacks, and multi-megabyte terminal output never
    leave the process. Pass process_inputs/process_outputs explicitly to override.
    """
    kwargs.setdefault("process_inputs", _scrub_inputs)
    kwargs.setdefault("process_outputs", _scrub_outputs)

    def deco(fn: F) -> F:
        try:
            from langsmith import traceable
        except ImportError:
            return fn
        decorate = cast(Callable[..., Callable[[F], F]], traceable)
        return decorate(name=name, run_type=run_type, **kwargs)(fn)

    return deco


def wrap_openai_client(client: Any, chat_name: str = "nemotron") -> Any:
    """Wrap an (Async)OpenAI client so every chat completion becomes an LLM run with token usage."""
    if not enabled():
        return client
    try:
        from langsmith.wrappers import wrap_openai
    except ImportError:
        return client
    return wrap_openai(client, chat_name=chat_name)


def annotate(metadata: dict[str, Any] | None = None, tags: list[str] | None = None) -> None:
    """Attach metadata or tags to the current run, if any."""
    if not enabled():
        return
    try:
        from langsmith.run_helpers import get_current_run_tree
    except ImportError:
        return
    rt = get_current_run_tree()
    if rt is None:
        return
    if metadata:
        rt.metadata.update(metadata)
    if tags:
        rt.tags = sorted({*(rt.tags or []), *tags})


def current_trace_url() -> str | None:
    """Best-effort link to the current trace for surfacing in the UI."""
    if not enabled():
        return None
    try:
        from langsmith.run_helpers import get_current_run_tree
    except ImportError:
        return None
    rt = get_current_run_tree()
    if rt is None:
        return None
    try:
        return str(rt.get_url())
    except Exception:  # noqa: BLE001
        return None
