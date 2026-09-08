"""Private session aggregate and validated lifecycle with server-side timing."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field

from app.schemas.candidate import CandidateProfile
from app.schemas.common import DomainModel
from app.schemas.evaluation import FinalReport, InterviewTurn, LiveEvaluation
from app.schemas.interview import (
    CandidateAnswer,
    DifficultyLevel,
    InterviewPlan,
    InterviewQuestion,
    InterviewSettings,
    PanelMember,
    SessionStatus,
)
from app.utils.errors import InvalidSessionState
from app.utils.helpers import utc_now

TRANSITIONS = {
    SessionStatus.CREATED: {SessionStatus.READY, SessionStatus.FAILED},
    SessionStatus.READY: {SessionStatus.IN_PROGRESS, SessionStatus.ENDING, SessionStatus.FAILED},
    SessionStatus.IN_PROGRESS: {SessionStatus.ENDING, SessionStatus.FAILED},
    SessionStatus.ENDING: {SessionStatus.COMPLETED, SessionStatus.FAILED},
    SessionStatus.FAILED: {SessionStatus.ENDING},
    SessionStatus.COMPLETED: set(),
}


class InterviewSession(DomainModel):
    """Never expose this private aggregate through candidate UI/API outputs."""

    session_id: UUID = Field(default_factory=uuid4)
    candidate: CandidateProfile
    settings: InterviewSettings
    status: SessionStatus = SessionStatus.CREATED
    created_at: AwareDatetime = Field(default_factory=utc_now)
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    current_difficulty: DifficultyLevel = DifficultyLevel.PROFESSIONAL
    plan: InterviewPlan | None = None
    panel: list[PanelMember] = Field(default_factory=list)
    questions: list[InterviewQuestion] = Field(default_factory=list)
    answers: list[CandidateAnswer] = Field(default_factory=list)
    turns: list[InterviewTurn] = Field(default_factory=list)
    live_evaluations: list[LiveEvaluation] = Field(default_factory=list)
    report: FinalReport | None = None
    failure_code: str | None = None

    def transition(self, status: SessionStatus, now: datetime | None = None) -> None:
        """Reject invalid transitions; time is injectable for deterministic tests."""
        if status not in TRANSITIONS[self.status]:
            raise InvalidSessionState(f"Cannot move from {self.status} to {status}.")
        now = now or utc_now()
        if now.tzinfo is None:
            raise InvalidSessionState("Session timestamps must include a timezone.")
        self.status = status
        if status == SessionStatus.IN_PROGRESS:
            self.started_at = now
        if status in {SessionStatus.ENDING, SessionStatus.FAILED} and self.ended_at is None:
            self.ended_at = now

    def elapsed_seconds(self, now: datetime | None = None) -> float:
        if self.started_at is None:
            return 0
        return max(0, ((self.ended_at or now or utc_now()) - self.started_at).total_seconds())

    def remaining_seconds(self, now: datetime | None = None) -> float:
        return max(0, self.settings.duration_minutes * 60 - self.elapsed_seconds(now))

    def is_near_end(self, now: datetime | None = None) -> bool:
        return self.remaining_seconds(now) <= 120

    def should_end(self, now: datetime | None = None) -> bool:
        return self.started_at is not None and self.remaining_seconds(now) <= 0
