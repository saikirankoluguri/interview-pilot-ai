"""Small provider-health contract with no model-runtime dependencies."""

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    status: Literal["healthy", "unhealthy"]
    mode: Literal["mock", "real"]
    latency_ms: float | None = None
    model: str | None = None
    device: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable, non-sensitive health summary."""
        return {key: value for key, value in asdict(self).items() if value is not None}
