"""Environment settings; real adapters require explicit Lightning mode."""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.interview import Difficulty

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", env_file_encoding="utf-8"
    )
    app_env: Literal["local", "lightning", "test"] = "local"
    llm_provider: Literal["mock", "qwen"] = "mock"
    stt_provider: Literal["mock", "whisper"] = "mock"
    tts_provider: Literal["mock", "kokoro"] = "mock"
    vad_provider: Literal["mock", "silero"] = "mock"
    llm_device: str = "cpu"
    llm_model: str = "qwen2.5:1.5b"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_timeout_seconds: float = Field(
        default=60,
        gt=0,
        le=300,
        validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS", "PROVIDER_TIMEOUT_SECONDS"),
    )
    llm_temperature: float = Field(default=0.1, ge=0, le=2)
    llm_max_output_tokens: int = Field(default=4096, ge=64, le=32768)
    whisper_model_size: str = "base.en"
    whisper_model_path: Path | None = None
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: str | None = "en"
    model_cache_dir: Path = ROOT / "models"
    allow_model_downloads: bool = False
    tts_device: str = "cpu"
    tts_voice: str = "af_heart"
    tts_speed: float = Field(default=1, ge=0.5, le=2)
    tts_sample_rate: Literal[24000] = 24000
    tts_model_path: Path | None = None
    tts_max_text_characters: int = Field(default=1000, ge=50, le=5000)
    kokoro_lang_code: str = "a"
    kokoro_model_path: Path | None = None
    kokoro_config_path: Path | None = None
    kokoro_voice_path: Path | None = None
    vad_device: str = "cpu"
    vad_model_path: Path | None = None
    vad_threshold: float = Field(default=0.5, gt=0, lt=1)
    vad_min_speech_ms: int = Field(default=250, ge=0, le=10000)
    vad_min_silence_ms: int = Field(
        default=700,
        ge=100,
        le=10000,
        validation_alias=AliasChoices("VAD_MIN_SILENCE_MS", "VAD_SILENCE_MS"),
    )
    provider_healthcheck_enabled: bool = False
    interview_default_duration_minutes: Literal[30, 60] = 30
    interview_default_difficulty: Difficulty = Difficulty.ADAPTIVE
    data_dir: Path = ROOT / "data"
    upload_dir: Path | None = None
    recording_dir: Path | None = None
    transcript_dir: Path | None = None
    report_dir: Path | None = None
    cache_dir: Path | None = None
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    max_pdf_pages: int = Field(default=20, ge=1, le=100)
    company_research_enabled: bool = False
    realtime_transport: Literal["gradio", "fastrtc"] = "gradio"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    server_name: str = "127.0.0.1"
    server_port: int = Field(default=7860, ge=1024, le=65535)

    @property
    def provider_timeout_seconds(self) -> float:
        """Compatibility accessor for the pre-Phase-1 setting name."""
        return self.llm_timeout_seconds

    @property
    def vad_silence_seconds(self) -> float:
        """Compatibility accessor for existing voice orchestration."""
        return self.vad_min_silence_ms / 1000

    @property
    def resolved_kokoro_model_path(self) -> Path | None:
        return self.tts_model_path or self.kokoro_model_path

    @field_validator("interview_default_duration_minutes", "tts_sample_rate", mode="before")
    @classmethod
    def parse_numeric_choice(cls, value: object) -> object:
        return int(value) if isinstance(value, str) else value

    @field_validator(
        "whisper_model_path",
        "tts_model_path",
        "kokoro_model_path",
        "kokoro_config_path",
        "kokoro_voice_path",
        "vad_model_path",
        mode="before",
    )
    @classmethod
    def blank_optional_path(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def safe_runtime(self) -> "Settings":
        providers = (self.llm_provider, self.stt_provider, self.tts_provider, self.vad_provider)
        if self.app_env != "lightning" and any(p != "mock" for p in providers):
            raise ValueError(
                "Real providers require APP_ENV=lightning; local/test uses mocks only."
            )
        if self.app_env != "lightning" and self.allow_model_downloads:
            raise ValueError("Model downloads are forbidden in local/test mode.")
        if self.company_research_enabled:
            raise ValueError("Company research is not implemented in V0.1.")
        for field, folder in (
            ("upload_dir", "uploads"),
            ("recording_dir", "recordings"),
            ("transcript_dir", "transcripts"),
            ("report_dir", "reports"),
            ("cache_dir", "cache"),
        ):
            if getattr(self, field) is None:
                setattr(self, field, self.data_dir / folder)
        return self


def get_settings() -> Settings:
    return Settings()
