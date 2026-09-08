"""Request a contextual strategy rather than generating a static interview script."""

from app.agents.requests import make_request
from app.interview.session import InterviewSession
from app.providers.llm.base import LLMProvider, LLMTask
from app.schemas.interview import InterviewPlan
from app.utils.errors import ProviderError


class InterviewPlannerAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def plan(self, session: InterviewSession) -> InterviewPlan:
        plan = await self.llm.generate_structured(
            make_request(LLMTask.PLAN, "interview_planner.md", session), InterviewPlan
        )
        if len(plan.panel) != session.settings.panel_size:
            raise ProviderError("Planner returned an invalid panel size.")
        if len(plan.topics) != len(plan.question_allocation) or any(
            n < 1 or n > 10 for n in plan.question_allocation
        ):
            raise ProviderError("Planner returned an invalid topic allocation.")
        plan.starting_difficulty = session.current_difficulty
        return plan
