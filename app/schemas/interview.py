"""Interview configuration, questions, panel identities, and public output."""

from enum import IntEnum, StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field

from app.schemas.common import DomainModel
from app.utils.helpers import utc_now


class InterviewRound(StrEnum):
    SCREENING = "screening"
    ROUND_1 = "round_1"
    ROUND_2 = "round_2"
    TECHNICAL = "technical"
    MANAGERIAL = "managerial"
    BEHAVIORAL = "behavioral"
    SYSTEM_DESIGN = "system_design"
    CUSTOM = "custom"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    ADAPTIVE = "adaptive"


class DifficultyLevel(IntEnum):
    FOUNDATION = 1
    BASIC_PRACTICAL = 2
    PROFESSIONAL = 3
    ADVANCED_SCENARIO = 4
    ARCHITECTURE_EXPERT = 5


class SessionStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    ENDING = "ending"
    COMPLETED = "completed"
    FAILED = "failed"


class InterviewSettings(DomainModel):
    """Explicit session choices, independent of process environment defaults."""

    target_role: str = Field(min_length=2, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    round: InterviewRound = InterviewRound.TECHNICAL
    duration_minutes: Literal[30, 60] = 30
    difficulty: Difficulty = Difficulty.ADAPTIVE
    panel_size: int = Field(default=1, ge=1, le=3)
    custom_round_description: str | None = Field(default=None, max_length=1000)


class PanelMember(DomainModel):
    name: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=100)
    focus_area: str = Field(min_length=1, max_length=200)
    voice_id: str | None = Field(default=None, max_length=100)


class InterviewQuestion(DomainModel):
    """Stable identity preserves question/answer alignment in final feedback."""

    question_id: UUID = Field(default_factory=uuid4)
    text: str = Field(min_length=5, max_length=800)
    topic: str = Field(min_length=1, max_length=200)
    difficulty: DifficultyLevel
    panel_index: int = Field(default=0, ge=0, le=2)
    asked_at: AwareDatetime = Field(default_factory=utc_now)


class CandidateAnswer(DomainModel):
    question_id: UUID
    text: str = Field(min_length=1, max_length=8000)
    answered_at: AwareDatetime = Field(default_factory=utc_now)


class InterviewPlan(DomainModel):
    topics: list[str] = Field(min_length=2, max_length=12)
    question_allocation: list[int] = Field(min_length=2, max_length=12)
    starting_difficulty: DifficultyLevel
    panel: list[PanelMember] = Field(min_length=1, max_length=3)
    resume_priorities: list[str] = Field(max_length=10)
    jd_priorities: list[str] = Field(max_length=10)


class InterviewMessage(DomainModel):
    """Only spoken text and public identity/state; no scores or hidden evaluation."""

    question: str = Field(min_length=1, max_length=800)
    panel_member: str
    ended: bool = False


InterviewType = InterviewRound
DifficultyMode = Difficulty
InterviewStatus = SessionStatus
