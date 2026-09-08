"""Normalize and validate pasted job descriptions locally."""

from app.utils.errors import DocumentParseError


def parse_job_description(text: str) -> str:
    normalized = " ".join(text.split())
    if not 50 <= len(normalized) <= 20000:
        raise DocumentParseError("Job description must contain 50 to 20,000 characters.")
    return normalized
