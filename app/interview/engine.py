"""Central interview orchestration with injected agents, policy, and private storage."""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from time import perf_counter
from uuid import UUID
from weakref import WeakValueDictionary

from app.agents.final_evaluator import FinalEvaluatorAgent
from app.agents.interviewer import InterviewerAgent
from app.agents.live_evaluator import LiveEvaluatorAgent
from app.evaluation.rubric import ScoringRubric
from app.evaluation.scoring import calculate_final_score, calculate_live_score
from app.interview.adaptive import AdaptivePolicy
from app.interview.planner import InterviewPlannerAgent
from app.interview.question_router import QuestionRouter
from app.interview.session import InterviewSession
from app.schemas.candidate import CandidateProfile
from app.schemas.evaluation import (
    AdaptiveAction,
    FinalReport,
    InterviewTurn,
    TurnLatencyMetrics,
)
from app.schemas.interview import (
    CandidateAnswer,
    InterviewMessage,
    InterviewQuestion,
    InterviewSettings,
    SessionStatus,
)
from app.storage.session_store import SessionStore
from app.utils.errors import InterviewError, InvalidSessionState, ProviderError
from app.utils.helpers import utc_now

logger = logging.getLogger(__name__)


class InterviewEngine:
    """Single-process POC; operations on the same session are serialized."""

    def __init__(
        self,
        *,
        planner: InterviewPlannerAgent,
        interviewer: InterviewerAgent,
        live_evaluator: LiveEvaluatorAgent,
        final_evaluator: FinalEvaluatorAgent,
        policy: AdaptivePolicy,
        router: QuestionRouter,
        store: SessionStore,
        rubric: ScoringRubric,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.planner = planner
        self.interviewer = interviewer
        self.live_evaluator = live_evaluator
        self.final_evaluator = final_evaluator
        self.policy = policy
        self.router = router
        self.store = store
        self.rubric = rubric
        self.clock = clock
        self._locks: WeakValueDictionary[UUID, asyncio.Lock] = WeakValueDictionary()

    def _lock(self, session_id: UUID) -> asyncio.Lock:
        lock = self._locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[session_id] = lock
        return lock

    def create_session(
        self, candidate: CandidateProfile, settings: InterviewSettings
    ) -> InterviewSession:
        if candidate.target_role != settings.target_role or candidate.company != settings.company:
            raise InterviewError("Candidate and interview role/company must match.")
        session = InterviewSession(
            candidate=candidate,
            settings=settings,
            created_at=self.clock(),
            current_difficulty=self.policy.initial_level(settings.difficulty),
        )
        self.store.save(session)
        return session

    def get_session(self, session_id: UUID) -> InterviewSession:
        session = self.store.get(session_id)
        if session is None:
            raise InterviewError("Interview session was not found.")
        return session

    async def _prepare(self, session: InterviewSession) -> None:
        if session.status != SessionStatus.CREATED:
            raise InvalidSessionState("Only a new session can be prepared.")
        session.plan = await self.planner.plan(session)
        session.panel = session.plan.panel
        session.transition(SessionStatus.READY, self.clock())
        self.store.save(session)

    async def prepare_session(self, session_id: UUID) -> InterviewSession:
        async with self._lock(session_id):
            session = self.get_session(session_id)
            await self._prepare(session)
            return session

    def _fail(self, session: InterviewSession, code: str) -> None:
        if session.status not in {SessionStatus.FAILED, SessionStatus.COMPLETED}:
            session.transition(SessionStatus.FAILED, self.clock())
        session.failure_code = code
        self.store.save(session)
        logger.warning("session=%s state=failed code=%s", session.session_id, code)

    async def start_interview(self, session_id: UUID) -> InterviewMessage:
        async with self._lock(session_id):
            session = self.get_session(session_id)
            if session.status not in {SessionStatus.CREATED, SessionStatus.READY}:
                raise InvalidSessionState("This interview has already started or ended.")
            try:
                if session.status == SessionStatus.CREATED:
                    await self._prepare(session)
                message = await self.interviewer.ask(session)
                session.transition(SessionStatus.IN_PROGRESS, self.clock())
                session.questions.append(
                    InterviewQuestion(
                        text=message.question,
                        topic=session.plan.topics[0],
                        difficulty=session.current_difficulty,
                        asked_at=self.clock(),
                    )
                )
                self.store.save(session)
                logger.info("session=%s state=in_progress", session_id)
                return InterviewMessage(
                    question=message.question, panel_member=session.panel[0].name
                )
            except InterviewError:
                self._fail(session, "start_failed")
                raise

    async def process_candidate_answer(self, session_id: UUID, text: str) -> InterviewMessage:
        """Internal text entry point; the candidate UI supplies microphone audio only."""
        async with self._lock(session_id):
            session = self.get_session(session_id)
            if session.status != SessionStatus.IN_PROGRESS:
                raise InvalidSessionState("The interview is not accepting answers.")
            if session.should_end(self.clock()):
                await self._end(session)
                return self._closing(session)
            question = session.questions[-1]
            if any(a.question_id == question.question_id for a in session.answers):
                raise InvalidSessionState("This question already has an answer.")
            answer = CandidateAnswer(
                question_id=question.question_id, text=text, answered_at=self.clock()
            )
            session.answers.append(answer)
            self.store.save(session)
            try:
                started = perf_counter()
                decision = await self.live_evaluator.evaluate(session)
                latency = TurnLatencyMetrics(llm_seconds=perf_counter() - started)
                evaluation = decision.evaluation
                evaluation.overall_score = calculate_live_score(evaluation, self.rubric)
                scores = [e.overall_score for e in session.live_evaluations] + [
                    evaluation.overall_score
                ]
                level = self.policy.next_level(
                    session.current_difficulty, scores, session.settings.difficulty
                )
                session.live_evaluations.append(evaluation)
                session.turns.append(
                    InterviewTurn(
                        question=question,
                        answer=answer,
                        evaluation=evaluation,
                        action=decision.action,
                        next_difficulty=level,
                        latency=latency,
                    )
                )
                session.current_difficulty = level
                # Persist the answer and hidden evaluation before finalization/next question.
                self.store.save(session)
                if (
                    decision.action == AdaptiveAction.END_INTERVIEW
                    or session.should_end(self.clock())
                    or len(session.answers) >= 100
                ):
                    await self._end(session)
                    return self._closing(session)
                if decision.next_question is None:
                    raise ProviderError("Live decision did not include the next question.")
                next_question = self.router.route(
                    decision.next_question,
                    session.questions,
                    session.plan.topics,
                    level,
                    len(session.panel),
                )
                next_question.asked_at = self.clock()
                session.questions.append(next_question)
                self.store.save(session)
                logger.info(
                    "session=%s turn=%d llm_seconds=%.3f",
                    session_id,
                    len(session.turns),
                    latency.llm_seconds,
                )
                return InterviewMessage(
                    question=next_question.text,
                    panel_member=session.panel[next_question.panel_index].name,
                )
            except InterviewError:
                self._fail(session, "turn_failed")
                raise

    def _closing(self, session: InterviewSession) -> InterviewMessage:
        panel_name = session.panel[0].name if session.panel else "Interviewer"
        return InterviewMessage(
            question="Thank you. The interview has ended. Your feedback is ready.",
            panel_member=panel_name,
            ended=True,
        )

    async def _end(self, session: InterviewSession) -> FinalReport:
        if session.status == SessionStatus.COMPLETED and session.report is not None:
            return session.report
        if session.status not in {
            SessionStatus.READY,
            SessionStatus.IN_PROGRESS,
            SessionStatus.FAILED,
            SessionStatus.ENDING,
        }:
            raise InvalidSessionState("This interview cannot be ended yet.")
        if session.status != SessionStatus.ENDING:
            session.transition(SessionStatus.ENDING, self.clock())
        self.store.save(session)
        try:
            report = await self.final_evaluator.evaluate(session)
            report.overall_score = calculate_final_score(report, self.rubric)
            self.store.save_report(report)
            session.report = report
            session.failure_code = None
            session.transition(SessionStatus.COMPLETED, self.clock())
            self.store.save(session)
            logger.info("session=%s state=completed", session.session_id)
            return report
        except InterviewError:
            self._fail(session, "final_evaluation_failed")
            raise

    async def end_interview(self, session_id: UUID) -> FinalReport:
        async with self._lock(session_id):
            return await self._end(self.get_session(session_id))

    async def save_latency(self, session_id: UUID, metrics: TurnLatencyMetrics) -> None:
        async with self._lock(session_id):
            session = self.get_session(session_id)
            if session.turns:
                metrics.llm_seconds = session.turns[-1].latency.llm_seconds
                session.turns[-1].latency = metrics
                self.store.save(session)
