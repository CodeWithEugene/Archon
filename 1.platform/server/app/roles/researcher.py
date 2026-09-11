"""Researcher: turns a failure into Tavily queries and the results into a short brief."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.core.router import Task
from app.grounding.tavily import Grounder, SearchResult
from app.llm.client import LLM, LLMError
from app.llm.prompts import research_brief_messages, research_query_messages

TavilyHook = Callable[[SearchResult], Awaitable[None]]


@dataclass
class ResearchBrief:
    brief: str
    sources: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    skipped_reason: str | None = None


class Researcher:
    def __init__(self, llm: LLM, grounder: Grounder, *, max_queries: int = 3) -> None:
        self.llm = llm
        self.grounder = grounder
        self.max_queries = max_queries

    async def research(self, failing_output: str, libraries: list[str], on_search: TavilyHook | None) -> ResearchBrief:
        try:
            obj, _ = await self.llm.complete_json(
                Task.RESEARCH_QUERIES, research_query_messages(failing_output, libraries), max_tokens=400
            )
        except LLMError as exc:
            return ResearchBrief(brief="", skipped_reason=f"query synthesis failed: {exc}")
        raw = obj.get("queries", [])
        queries = [str(q).strip() for q in raw if str(q).strip()][: self.max_queries] if isinstance(raw, list) else []
        if not queries:
            return ResearchBrief(brief="", skipped_reason="no queries produced")

        results: list[SearchResult] = []
        for q in queries:
            r = await self.grounder.search(q)
            results.append(r)
            if on_search is not None:
                await on_search(r)
        texts = [r.as_text() for r in results if r.hits]
        if not texts:
            reason = "; ".join(sorted({r.error or "no results" for r in results}))
            return ResearchBrief(brief="", queries=queries, skipped_reason=f"search returned nothing ({reason})")

        try:
            obj2, _ = await self.llm.complete_json(
                Task.RESEARCH_BRIEF, research_brief_messages("\n\n".join(texts)), max_tokens=900
            )
        except LLMError as exc:
            # Fall back to raw snippets so the engineer still gets something grounded.
            joined = "\n\n".join(texts)[:8000]
            return ResearchBrief(
                brief=joined,
                queries=queries,
                sources=_urls(results),
                skipped_reason=f"brief synthesis failed: {exc}",
            )
        brief = str(obj2.get("brief", "")).strip()
        sources = (
            [str(s) for s in obj2.get("sources", []) if isinstance(s, str)]
            if isinstance(obj2.get("sources"), list)
            else []
        )
        return ResearchBrief(brief=brief, sources=sources or _urls(results), queries=queries)


def _urls(results: list[SearchResult]) -> list[str]:
    seen: dict[str, None] = {}
    for r in results:
        for h in r.hits:
            if h.url:
                seen.setdefault(h.url, None)
    return list(seen)[:10]
