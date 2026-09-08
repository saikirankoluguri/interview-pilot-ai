"""Small pure helpers; avoid putting domain behavior in a utility module."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for future session metadata."""
    return datetime.now(UTC)
