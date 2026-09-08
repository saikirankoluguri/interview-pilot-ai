"""One structured model call supplies evaluation, action, and next spoken question."""

from app.agents.requests import make_request
from app.evaluation.rubric import ScoringRubric
from app.interview.session import InterviewSession
from app.providers.llm.base import LLMProvider, LLMTask
from app.schemas.evaluation import LiveTurnDecision


class LiveEvaluatorAgent:
    def __init__(self, llm: LLMProvider, rubric: ScoringRubric) -> None:
        self.llm = llm
        self.rubric = rubric

    async def evaluate(self, session: InterviewSession) -> LiveTurnDecision:
        instructions = "Apply this controller policy: " + self.rubric.model_dump_json()
        instructions += f" Remaining time: {session.remaining_seconds():.0f} seconds."
        return await self.llm.generate_structured(
            make_request(LLMTask.LIVE_DECISION, "live_evaluator.md", session, instructions),
            LiveTurnDecision,
        )
