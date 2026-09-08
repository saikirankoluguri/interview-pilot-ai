"""Validation, lifecycle, timer, routing, and rolling-policy checks."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.config.settings import Settings
from app.evaluation.rubric import load_rubric
from app.interview.adaptive import AdaptivePolicy
from app.interview.question_router import QuestionRouter, fingerprint
from app.interview.session import InterviewSession
from app.schemas.candidate import CandidateProfile
from app.schemas.interview import (
    Difficulty,
    DifficultyLevel,
    InterviewQuestion,
    InterviewSettings,
    SessionStatus,
)
from app.utils.errors import InvalidSessionState


@pytest.mark.parametrize(
    "field,value", [("name", " "), ("resume_text", "short"), ("job_description", "short")]
)
def test_candidate_validation(candidate, field, value):
    data = candidate.model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate(data)


@pytest.mark.parametrize("panel", [0, 4])
def test_panel_validation(panel):
    with pytest.raises(ValidationError):
        InterviewSettings(target_role="Engineer", panel_size=panel)


@pytest.mark.parametrize("duration", [0, 45, 90])
def test_duration_validation(duration):
    with pytest.raises(ValidationError):
        InterviewSettings(target_role="Engineer", duration_minutes=duration)


@pytest.mark.parametrize(
    "provider", ["llm_provider", "stt_provider", "tts_provider", "vad_provider"]
)
def test_local_guard(provider):
    real = dict(
        llm_provider="qwen", stt_provider="whisper", tts_provider="kokoro", vad_provider="silero"
    )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{provider: real[provider]})


@pytest.mark.parametrize(
    "scores,current,expected",
    [
        ([90], 3, 3),
        ([20], 3, 3),
        ([85, 88], 3, 4),
        ([35, 30], 3, 2),
        ([70, 75], 3, 3),
        ([90, 20], 3, 3),
        ([85, 88], 5, 5),
        ([20, 30], 1, 1),
        ([100, 100, 100], 1, 2),
        ([0, 0, 0], 5, 4),
        ([45, 45], 3, 3),
    ],
)
def test_adaptive(scores, current, expected):
    policy = AdaptivePolicy(load_rubric().adaptive)
    assert policy.next_level(DifficultyLevel(current), scores) == expected
    assert policy.rolling_score([20, 60, 100]) == 72
    assert policy.next_level(DifficultyLevel(4), [0, 0], Difficulty.HARD) == 4


def test_lifecycle_and_timer(candidate):
    session = InterviewSession(
        candidate=candidate, settings=InterviewSettings(target_role=candidate.target_role)
    )
    with pytest.raises(InvalidSessionState):
        session.transition(SessionStatus.COMPLETED)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    session.transition(SessionStatus.READY, now)
    session.transition(SessionStatus.IN_PROGRESS, now)
    assert session.remaining_seconds(now + timedelta(minutes=10)) == 1200
    assert session.is_near_end(now + timedelta(minutes=29))
    assert session.should_end(now + timedelta(minutes=31))
    session.transition(SessionStatus.ENDING, now + timedelta(minutes=10))
    assert session.elapsed_seconds(now + timedelta(hours=1)) == 600
    session.transition(SessionStatus.COMPLETED, now)
    with pytest.raises(InvalidSessionState):
        session.transition(SessionStatus.IN_PROGRESS)


def test_router_duplicate_and_topic_protection():
    router = QuestionRouter()
    question = InterviewQuestion(text="Explain your API design?", topic="API", difficulty=3)
    result = router.route(question, [question], ["API", "testing"], DifficultyLevel(4), 2)
    assert fingerprint(result.text) != fingerprint(question.text)
    assert result.difficulty == 4
    history = [question.model_copy(deep=True) for _ in range(3)]
    assert (
        router.route(question, history, ["API", "testing"], DifficultyLevel(3), 2).topic
        == "testing"
    )
