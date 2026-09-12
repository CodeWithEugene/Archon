"""Log compactor and narrator: cheap Nemotron 3 Nano / Super calls, each optional."""

from __future__ import annotations

from app.core.router import Task
from app.llm.client import LLM, LLMError
from app.llm.prompts import compact_messages, narrate_messages
from app.observability.tracing import traced
from app.sandbox.pytest_parser import failing_excerpt

COMPACT_THRESHOLD_CHARS = 16_000


class Compactor:
    def __init__(self, llm: LLM, *, threshold: int = COMPACT_THRESHOLD_CHARS) -> None:
        self.llm = llm
        self.threshold = threshold

    @traced("compactor.compact")
    async def compact(self, output: str) -> str:
        excerpt = failing_excerpt(output)
        if len(excerpt) <= self.threshold:
            return excerpt
        try:
            comp = await self.llm.complete(Task.COMPACT_LOGS, compact_messages(excerpt), max_tokens=2500)
            text = comp.text.strip()
            return text or excerpt[-self.threshold :]
        except LLMError:
            return excerpt[-self.threshold :]


class Narrator:
    """Produces the one-line 'thought' shown before each step. Templates by default; Super if enabled."""

    TEMPLATES: dict[str, str] = {
        "PROVISIONING": "Cloning the repository and installing dependencies in a fresh sandbox.",
        "REPRODUCING": "Running the test suite on the untouched checkout to record the baseline.",
        "GROUNDING": "Searching current documentation and issue threads for the failure signature.",
        "REASONING": "Asking Nemotron 3 Ultra for a root cause and candidate patches.",
        "TESTING": "Applying each candidate on its own sandbox fork and re-running the tests.",
        "REVIEWING": "Checking the winning patch for deleted tests, unrelated changes, and secrets.",
    }

    def __init__(self, llm: LLM | None = None, *, use_model: bool = False) -> None:
        self.llm = llm
        self.use_model = use_model and llm is not None

    async def narrate(self, state: str, detail: str = "") -> str:
        base = self.TEMPLATES.get(state, state.title())
        if not self.use_model or self.llm is None:
            return f"{base} {detail}".strip()
        try:
            comp = await self.llm.complete(Task.NARRATE, narrate_messages(state, detail or base), max_tokens=60)
            return comp.text.strip().splitlines()[0][:200] if comp.text.strip() else base
        except LLMError:
            return base
