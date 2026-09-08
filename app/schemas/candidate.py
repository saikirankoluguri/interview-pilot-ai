"""Minimal private candidate profile; no contact fields are collected."""

from pydantic import Field

from app.schemas.common import DomainModel


class CandidateProfile(DomainModel):
    """Context retained only in private local/Studio session storage."""

    name: str = Field(min_length=1, max_length=100)
    target_role: str = Field(min_length=2, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    resume_text: str = Field(min_length=30, max_length=40000)
    job_description: str = Field(min_length=50, max_length=20000)
    notes: str | None = Field(default=None, max_length=2000)


CandidateContext = CandidateProfile
