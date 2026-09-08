"""Deep structured evaluation after the live interview ends."""

from app.agents.requests import PROMPTS, make_request
from app.interview.session import InterviewSession
from app.providers.llm.base import LLMProvider, LLMTask
from app.schemas.evaluation import FinalReport
from app.schemas.interview import SessionStatus
from app.utils.errors import InvalidSessionState, ProviderError


class FinalEvaluatorAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def evaluate(self, session: InterviewSession) -> FinalReport:
        if session.status != SessionStatus.ENDING:
            raise InvalidSessionState("Final evaluation requires an ended interview.")
        report = await self.llm.generate_structured(
            make_request(
                LLMTask.FINAL_EVALUATION,
                "final_evaluator.md",
                session,
                (PROMPTS / "feedback.md").read_text(encoding="utf-8"),
            ),
            FinalReport,
        )
        expected = [q.question_id for q in session.questions]
        if (
            report.session_id != session.session_id
            or [q.question_id for q in report.questions] != expected
        ):
            raise ProviderError("Final report does not match the recorded interview questions.")
        answers = {a.question_id: a.text for a in session.answers}
        for question, feedback in zip(session.questions, report.questions, strict=True):
            feedback.question = question.text
            feedback.answer_transcript = answers.get(question.question_id, "No answer recorded.")
        return report
