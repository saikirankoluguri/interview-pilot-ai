"""Private live decisions and complete post-interview feedback contracts."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.schemas.common import DomainModel
from app.schemas.interview import CandidateAnswer, DifficultyLevel, InterviewQuestion
from app.utils.helpers import utc_now

Score = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class AdaptiveAction(StrEnum):
    FOLLOW_UP = "follow_up"
    SAME_LEVEL = "same_level"
    INCREASE_DEPTH = "increase_depth"
    DECREASE_DEPTH = "decrease_depth"
    CHANGE_TOPIC = "change_topic"
    CLARIFY = "clarify"
    MOVE_ON = "move_on"
    END_INTERVIEW = "end_interview"


class LiveEvaluation(DomainModel):
    overall_score: Score
    correctness: Score
    relevance: Score
    depth: Score
    evidence: Score
    missing_concepts: list[str] = Field(default_factory=list, max_length=15)
    rationale: str = Field(max_length=1000)
    suggested_next_difficulty: DifficultyLevel


class LiveTurnDecision(DomainModel):
    """One LLM response; deterministic controller validates the proposal locally."""

    evaluation: LiveEvaluation
    action: AdaptiveAction
    next_difficulty: DifficultyLevel
    next_question: InterviewQuestion | None


class TurnLatencyMetrics(DomainModel):
    started_at: AwareDatetime = Field(default_factory=utc_now)
    speech_end_at: AwareDatetime | None = None
    stt_started_at: AwareDatetime | None = None
    stt_ended_at: AwareDatetime | None = None
    llm_started_at: AwareDatetime | None = None
    llm_ended_at: AwareDatetime | None = None
    tts_started_at: AwareDatetime | None = None
    tts_ended_at: AwareDatetime | None = None
    audio_playback_ready_at: AwareDatetime | None = None
    stt_seconds: float = Field(default=0, ge=0)
    llm_seconds: float = Field(default=0, ge=0)
    tts_seconds: float = Field(default=0, ge=0)
    total_seconds: float = Field(default=0, ge=0)
    speech_end_to_audio_ready_seconds: float = Field(default=0, ge=0)
    time_to_first_audio_seconds: float | None = Field(default=None, ge=0)

    @property
    def stt_ms(self) -> float:
        return self.stt_seconds * 1000

    @property
    def llm_ms(self) -> float:
        return self.llm_seconds * 1000

    @property
    def tts_ms(self) -> float:
        return self.tts_seconds * 1000

    @property
    def total_processing_ms(self) -> float:
        return self.total_seconds * 1000

    @property
    def speech_end_to_audio_ready_ms(self) -> float:
        return self.speech_end_to_audio_ready_seconds * 1000


class InterviewTurn(DomainModel):
    question: InterviewQuestion
    answer: CandidateAnswer
    evaluation: LiveEvaluation
    action: AdaptiveAction
    next_difficulty: DifficultyLevel
    latency: TurnLatencyMetrics = Field(default_factory=TurnLatencyMetrics)


class QuestionFeedback(DomainModel):
    question_id: UUID
    question: str
    answer_transcript: str
    score: Score
    done_well: list[str]
    missing: list[str]
    interviewer_expected: str
    ideal_answer: str
    recommended_topics: list[str]


class FinalReport(DomainModel):
    session_id: UUID
    generated_at: AwareDatetime = Field(default_factory=utc_now)
    overall_score: Score
    technical_score: Score
    relevance_score: Score
    communication_score: Score
    depth_score: Score
    practical_experience_score: Score
    strengths: list[str]
    weaknesses: list[str]
    questions: list[QuestionFeedback]
    weak_topics: list[str]
    preparation_recommendations: list[str]
    next_mock_focus: str
    is_mock: bool = False


FinalQuestionFeedback = QuestionFeedback
FinalInterviewReport = FinalReport
