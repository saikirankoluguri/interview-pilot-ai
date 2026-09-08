"""Reserve optional company-specific research for M8; no web access now."""

from app.providers.llm.base import LLMProvider


class ResearchAgent:
    """Logical agent using prompts/research.md; independent of model vendor."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def research(self, company_name: str) -> str:
        """Reserve optional company-specific research for M8; no web access now."""
        # TODO: Load prompt, invoke the injected provider, and validate output.
        raise NotImplementedError("ResearchAgent behavior is deferred.")
