"""Application errors with safe messages suitable for the UI boundary."""


class InterviewError(Exception):
    """Base error; messages must never contain candidate data or provider payloads."""


class ConfigurationError(InterviewError):
    """Invalid or unsafe application configuration."""


class ProviderError(InterviewError):
    """Base class for safe provider failures exposed at application boundaries."""


class ProviderUnavailableError(ProviderError):
    """A configured provider service cannot currently be reached."""


class ProviderInitializationError(ProviderError):
    """An optional runtime or configured model could not be initialized."""


class ProviderInferenceError(ProviderError):
    """A provider initialized successfully but inference failed."""


class ProviderResponseValidationError(ProviderError):
    """A provider returned malformed output or output outside the requested schema."""


class DocumentParseError(InterviewError):
    """Unsupported, oversized, or unreadable document."""


class InvalidSessionState(InterviewError):
    """Operation is incompatible with the current session or voice state."""


class AudioProcessingError(InterviewError):
    """Invalid audio or failed voice processing."""


class StorageError(InterviewError):
    """Unsafe path or failed persistence operation."""
