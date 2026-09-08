"""Application errors with safe messages suitable for the UI boundary."""


class InterviewError(Exception):
    """Base error; messages must never contain candidate data or provider payloads."""


class ConfigurationError(InterviewError):
    """Invalid or unsafe application configuration."""


class ProviderError(InterviewError):
    """Unavailable provider or invalid model output."""


class DocumentParseError(InterviewError):
    """Unsupported, oversized, or unreadable document."""


class InvalidSessionState(InterviewError):
    """Operation is incompatible with the current session or voice state."""


class AudioProcessingError(InterviewError):
    """Invalid audio or failed voice processing."""


class StorageError(InterviewError):
    """Unsafe path or failed persistence operation."""
