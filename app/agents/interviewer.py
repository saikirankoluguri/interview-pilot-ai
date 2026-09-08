"""Concise greeting/opening agent; later questions share the live decision call."""

from app.agents.requests import make_request
from app.interview.session import InterviewSession
from app.providers.llm.base import LLMProvider, LLMTask
from app.schemas.interview import InterviewMessage


class InterviewerAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def ask(self, session: InterviewSession) -> InterviewMessage:
        return await self.llm.generate_structured(
            make_request(LLMTask.OPENING, "interviewer.md", session), InterviewMessage
        )
