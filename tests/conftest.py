"""Synthetic fixtures and a hard network ban for every automated test."""

import socket
import sys
from pathlib import Path

import pytest

from app.config.settings import Settings
from app.schemas.candidate import CandidateProfile


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch):
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
        monkeypatch.delenv(field.lower(), raising=False)
    monkeypatch.setenv("GRADIO_ANALYTICS_ENABLED", "False")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    original_connect = socket.socket.connect

    def deny(*args, **kwargs):
        caller = sys._getframe(1)
        if caller.f_globals.get("__name__") == "socket" and caller.f_code.co_name in {
            "socketpair",
            "_fallback_socketpair",
        }:
            return original_connect(*args, **kwargs)
        raise AssertionError("Tests must not access the network.")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)


@pytest.fixture
def candidate() -> CandidateProfile:
    return CandidateProfile(
        name="Alex",
        target_role="QA Automation Engineer",
        resume_text="Synthetic profile: built API services and automated verification workflows.",
        job_description="Design reliable software and automated API tests, "
        "investigate failures, and collaborate on delivery.",
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path)
