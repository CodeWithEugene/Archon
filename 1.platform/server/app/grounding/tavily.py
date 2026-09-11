"""Tavily Search API wrapper with timeout, per-mission cache, and a fake for tests."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    title: str
    url: str
    content: str
    score: float = 0.0


@dataclass
class SearchResult:
    query: str
    hits: list[SearchHit]
    ms: int
    error: str | None = None
    cached: bool = False

    def as_text(self, limit_per_hit: int = 2500) -> str:
        blocks = []
        for h in self.hits:
            body = h.content[:limit_per_hit]
            blocks.append(f"### {h.title}\nURL: {h.url}\n{body}")
        return "\n\n".join(blocks)


class Grounder(Protocol):
    async def search(self, query: str) -> SearchResult: ...


@dataclass
class TavilyGrounder:
    api_key: str
    timeout_s: float = 10.0
    max_results: int = 5
    search_depth: str = "advanced"
    _cache: dict[str, SearchResult] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        from tavily import AsyncTavilyClient

        self._client = AsyncTavilyClient(api_key=self.api_key)

    async def search(self, query: str) -> SearchResult:
        key = hashlib.sha256(query.encode()).hexdigest()
        if key in self._cache:
            cached = self._cache[key]
            return SearchResult(query=query, hits=cached.hits, ms=0, cached=True)
        started = time.monotonic()
        try:
            raw: dict[str, Any] = await asyncio.wait_for(
                self._client.search(
                    query=query,
                    search_depth=self.search_depth,
                    max_results=self.max_results,
                    include_raw_content=False,
                ),
                timeout=self.timeout_s,
            )
        except TimeoutError:
            ms = int((time.monotonic() - started) * 1000)
            logger.warning("tavily timeout after %sms for %r", ms, query)
            return SearchResult(query=query, hits=[], ms=ms, error="timeout")
        except Exception as exc:
            ms = int((time.monotonic() - started) * 1000)
            logger.warning("tavily error for %r: %s", query, exc)
            return SearchResult(query=query, hits=[], ms=ms, error=type(exc).__name__)
        hits = [
            SearchHit(
                title=str(r.get("title", "")),
                url=str(r.get("url", "")),
                content=str(r.get("content", "")),
                score=float(r.get("score", 0.0) or 0.0),
            )
            for r in raw.get("results", [])
        ]
        result = SearchResult(query=query, hits=hits, ms=int((time.monotonic() - started) * 1000))
        self._cache[key] = result
        return result


class FakeGrounder:
    def __init__(self, hits: list[SearchHit] | None = None, error: str | None = None) -> None:
        self.hits = hits or []
        self.error = error
        self.queries: list[str] = []

    async def search(self, query: str) -> SearchResult:
        self.queries.append(query)
        return SearchResult(query=query, hits=[] if self.error else self.hits, ms=5, error=self.error)


class DisabledGrounder:
    async def search(self, query: str) -> SearchResult:
        return SearchResult(query=query, hits=[], ms=0, error="disabled")
