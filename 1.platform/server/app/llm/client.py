"""LLM client over Nebius Token Factory with usage accounting, retries, and a fake for tests."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from app.core.pricing import PriceTable
from app.core.router import ModelRouter, Task
from app.observability.tracing import wrap_openai_client

logger = logging.getLogger(__name__)

UsageHook = Callable[[str, str, int, int, float], Awaitable[None]]
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
MAX_THINKING_TOKENS = 24_000


class LLMError(RuntimeError):
    pass


@dataclass
class Completion:
    model: str
    text: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class LLM(Protocol):
    async def complete(
        self,
        task: Task,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> Completion: ...

    async def complete_json(
        self,
        task: Task,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
    ) -> tuple[dict[str, Any], Completion]: ...


def strip_reasoning(text: str) -> str:
    """Nemotron 3 reasoning models may emit <think> blocks. Remove them before parsing."""
    return THINK_RE.sub("", text).strip()


def extract_json_object(text: str) -> dict[str, Any]:
    text = strip_reasoning(text)
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMError("no JSON object found in model output")
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"model output is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise LLMError("model output JSON is not an object")
    return obj


class NebiusLLM:
    """AsyncOpenAI pointed at Nebius Token Factory. Records usage and cost per call."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        router: ModelRouter,
        prices: PriceTable,
        usage_hook: UsageHook | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = wrap_openai_client(
            AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=180.0), chat_name="nemotron"
        )
        self._router = router
        self._prices = prices
        self._usage_hook = usage_hook
        self._max_retries = max_retries

    async def complete(
        self,
        task: Task,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> Completion:
        model = self._router.model_for(task)
        try:
            return await self._call(model, task, messages, max_tokens, temperature, json_mode)
        except LLMError:
            fallback = self._router.fallback_for(model)
            if fallback is None:
                raise
            logger.warning("model %s unavailable for %s; falling back to %s", model, task, fallback)
            return await self._call(fallback, task, messages, max_tokens, temperature, json_mode)

    async def complete_json(
        self,
        task: Task,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
    ) -> tuple[dict[str, Any], Completion]:
        comp = await self.complete(task, messages, max_tokens=max_tokens, json_mode=True)
        try:
            return extract_json_object(comp.text), comp
        except LLMError as first:
            retry_msgs = [
                *messages,
                {"role": "assistant", "content": comp.text[:8000]},
                {
                    "role": "user",
                    "content": "That was not valid JSON. Output only the JSON object, nothing else.",
                },
            ]
            comp2 = await self.complete(task, retry_msgs, max_tokens=max_tokens, json_mode=True)
            try:
                return extract_json_object(comp2.text), comp2
            except LLMError as second:
                raise LLMError(f"invalid JSON twice: {first}; {second}") from second

    async def _call(
        self,
        model: str,
        task: Task,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> Completion:
        delay = 1.0
        last: Exception | None = None
        think = self._router.thinking_for(task)
        for attempt in range(self._max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    # Nemotron 3 reasons before answering. Reasoning tokens count against max_tokens and can
                    # leave `content` empty, so thinking is enabled only for tasks that need it.
                    "extra_body": {"chat_template_kwargs": {"enable_thinking": think}},
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                choice = resp.choices[0]
                text = (choice.message.content or "").strip()
                truncated = choice.finish_reason == "length"
                no_answer = not text or (json_mode and "{" not in text)
                if truncated and no_answer:
                    # Reasoning (sometimes emitted into `content`) consumed the budget before the answer.
                    if think and max_tokens < MAX_THINKING_TOKENS:
                        max_tokens = min(max_tokens * 2, MAX_THINKING_TOKENS)
                        logger.warning(
                            "%s hit max_tokens while reasoning; retrying with max_tokens=%d", model, max_tokens
                        )
                        continue
                    if think:
                        think = False
                        logger.warning(
                            "%s still truncated at max_tokens=%d; retrying with thinking off", model, max_tokens
                        )
                        continue
                    raise LLMError(f"{model}: no answer, output hit max_tokens={max_tokens}")
                pt = resp.usage.prompt_tokens if resp.usage else 0
                ct = resp.usage.completion_tokens if resp.usage else 0
                cost = self._prices.cost(model, pt, ct)
                if self._usage_hook is not None:
                    await self._usage_hook(model, str(task), pt, ct, cost)
                return Completion(model=model, text=text, prompt_tokens=pt, completion_tokens=ct, cost_usd=cost)
            except (RateLimitError, APIConnectionError) as exc:
                last = exc
            except APIStatusError as exc:
                last = exc
                if exc.status_code < 500 and exc.status_code != 429:
                    raise LLMError(f"{model}: HTTP {exc.status_code}: {exc.message}") from exc
            if attempt < self._max_retries:
                logger.warning("LLM call to %s failed (%s); retry in %.1fs", model, last, delay)
                await asyncio.sleep(delay)
                delay *= 2
        raise LLMError(f"{model}: giving up after {self._max_retries + 1} attempts: {last}")


class FakeLLM:
    """Scripted responses keyed by task. Each task has a FIFO queue of responses."""

    def __init__(
        self,
        scripts: dict[Task, list[str]] | None = None,
        router: ModelRouter | None = None,
        usage_hook: UsageHook | None = None,
        cost_per_call: float = 0.001,
    ) -> None:
        self.scripts: dict[Task, list[str]] = {k: list(v) for k, v in (scripts or {}).items()}
        self.calls: list[tuple[Task, list[dict[str, str]]]] = []
        self._router = router
        self._usage_hook = usage_hook
        self.cost_per_call = cost_per_call

    def push(self, task: Task, *responses: str) -> None:
        self.scripts.setdefault(task, []).extend(responses)

    async def complete(
        self,
        task: Task,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> Completion:
        self.calls.append((task, messages))
        queue = self.scripts.get(task) or []
        if not queue:
            raise LLMError(f"FakeLLM has no scripted response for {task}")
        text = queue.pop(0)
        model = self._router.model_for(task) if self._router else f"fake/{task}"
        if self._usage_hook is not None:
            await self._usage_hook(model, str(task), 1000, 100, self.cost_per_call)
        return Completion(
            model=model, text=text, prompt_tokens=1000, completion_tokens=100, cost_usd=self.cost_per_call
        )

    async def complete_json(
        self,
        task: Task,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
    ) -> tuple[dict[str, Any], Completion]:
        comp = await self.complete(task, messages, max_tokens=max_tokens, json_mode=True)
        return extract_json_object(comp.text), comp
