"""Provider timing values shared by verification and CPU benchmark tools."""

from dataclasses import dataclass


def safe_ratio(numerator: float, denominator: float) -> float | None:
    """Return a timing ratio, or None when no meaningful denominator exists."""
    if denominator <= 0:
        return None
    return numerator / denominator


@dataclass(frozen=True)
class ProviderOperationMetrics:
    operation: str
    duration_seconds: float
    audio_duration_seconds: float | None = None
    token_count: int | None = None
    time_to_first_response_seconds: float | None = None
    tokens_per_second: float | None = None

    @property
    def realtime_factor(self) -> float | None:
        if self.audio_duration_seconds is None:
            return None
        return safe_ratio(self.duration_seconds, self.audio_duration_seconds)

    @property
    def generation_ratio(self) -> float | None:
        if self.audio_duration_seconds is None:
            return None
        return safe_ratio(self.duration_seconds, self.audio_duration_seconds)
