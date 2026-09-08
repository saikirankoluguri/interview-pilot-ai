"""Small foundation checks; no model runtime, network, or Gradio server."""

import importlib
import pkgutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

import app
from app.config.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_all_application_modules_import() -> None:
    """Cloud stubs and UI modules must import without GPU or Gradio loading."""
    for module in pkgutil.walk_packages(app.__path__, prefix="app."):
        importlib.import_module(module.name)


def test_settings_defaults_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults remain mock; supported environment overrides are validated."""
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
        monkeypatch.delenv(field.lower(), raising=False)
    settings = Settings(_env_file=None)
    assert settings.app_env == "local"
    assert [
        settings.llm_provider,
        settings.stt_provider,
        settings.tts_provider,
        settings.vad_provider,
    ] == ["mock"] * 4
    assert settings.interview_default_duration_minutes == 30
    assert settings.interview_default_difficulty == "adaptive"
    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
    monkeypatch.setenv("APP_ENV", "lightning")
    assert Settings(_env_file=None).llm_provider == "qwen"
    monkeypatch.setenv("LLM_PROVIDER", "unknown")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_yaml_documents_parse() -> None:
    """Parse all checked-in YAML, including deployment and CI scaffolds."""
    paths = list((ROOT / "configs").glob("*.yaml")) + [
        ROOT / "deployment/docker/docker-compose.yml",
        ROOT / ".github/workflows/tests.yml",
    ]
    for path in paths:
        assert isinstance(yaml.safe_load(path.read_text(encoding="utf-8")), dict), path


def test_example_environment_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both documented dotenv examples must load without initializing providers."""
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
        monkeypatch.delenv(field.lower(), raising=False)
    local = Settings(_env_file=ROOT / ".env.example")
    assert local.interview_default_duration_minutes == 30
    assert (local.llm_provider, local.stt_provider, local.tts_provider, local.vad_provider) == (
        "mock",
        "mock",
        "mock",
        "mock",
    )
    cloud = Settings(_env_file=ROOT / "deployment/lightning/lightning.env.example")
    assert (cloud.llm_provider, cloud.stt_provider, cloud.tts_provider, cloud.vad_provider) == (
        "qwen",
        "whisper",
        "kokoro",
        "silero",
    )
    monkeypatch.setenv("INTERVIEW_DEFAULT_DURATION_MINUTES", "60")
    assert Settings(_env_file=None).interview_default_duration_minutes == 60
    monkeypatch.setenv("INTERVIEW_DEFAULT_DURATION_MINUTES", "45")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
