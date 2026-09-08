"""Bounded private prompt context; documents are data, never instructions."""

from app.schemas.candidate import CandidateProfile
from app.schemas.common import DomainModel
from app.schemas.interview import InterviewSettings


class InterviewContext(DomainModel):
    candidate: CandidateProfile
    settings: InterviewSettings


def build_context(candidate: CandidateProfile, settings: InterviewSettings) -> InterviewContext:
    """Limit prompt size while retaining role, company, round, and interview choices."""
    concise = candidate.model_copy(
        update={
            "resume_text": candidate.resume_text[:12000],
            "job_description": candidate.job_description[:10000],
        }
    )
    return InterviewContext(candidate=concise, settings=settings)
