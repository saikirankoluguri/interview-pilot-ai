"""Phase 1 real-provider behavior using HTTP mocks and fake CPU runtimes only."""

import argparse
import asyncio
import json
import sys
from types import SimpleNamespace

import httpx
import numpy as np
import pytest

from app.config.settings import Settings
from app.providers.factory import create_providers
from app.providers.llm.base import LLMRequest, LLMTask
from app.providers.llm.qwen import QwenProvider
from app.providers.metrics import ProviderOperationMetrics, safe_ratio
from app.providers.stt.whisper import WhisperProvider
from app.providers.tts.kokoro import KokoroProvider
from app.providers.vad.silero import SileroProvider
from app.schemas.audio import AudioBuffer
from app.schemas.evaluation import LiveTurnDecision
from app.utils.errors import (
    AudioProcessingError,
    ProviderResponseValidationError,
    ProviderUnavailableError,
)
from scripts.benchmark_cpu_providers import parser as benchmark_parser
from scripts.verify_real_providers import parser as verification_parser


def cloud_settings(**overrides):
    return Settings(_env_file=None, app_env="lightning", **overrides)


REQUEST = LLMRequest(
    task=LLMTask.LIVE_DECISION,
    instructions="Return one structured decision.",
    context_json="{}",
)


def test_qwen_live_decision_payload_metrics_and_health():
    requests = []
    decision = {
        "evaluation": {
            "overall_score": 78,
            "correctness": 80,
            "relevance": 82,
            "depth": 72,
            "evidence": 74,
            "missing_concepts": ["failure recovery"],
            "rationale": "Synthetic fixture.",
            "suggested_next_difficulty": 3,
        },
        "action": "follow_up",
        "next_difficulty": 3,
        "next_question": {
            "text": "How did you validate the failure-recovery design?",
            "topic": "reliability",
            "difficulty": 3,
        },
    }

    def respond(request):
        requests.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "fixture"}]})
        return httpx.Response(
            200,
            json={
                "message": {"content": json.dumps(decision)},
                "eval_count": 20,
                "eval_duration": 2_000_000_000,
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            provider = QwenProvider(
                cloud_settings(
                    llm_temperature=0.25,
                    llm_max_output_tokens=512,
                    llm_model="fixture-model",
                ),
                client,
            )
            result = await provider.generate_structured(REQUEST, LiveTurnDecision)
            health = await provider.health_check()
            assert result.action == "follow_up" and result.next_question is not None
            payload = json.loads(requests[0].content)
            assert payload["options"] == {"temperature": 0.25, "num_predict": 512}
            assert payload["format"]["title"] == "LiveTurnDecision"
            assert provider.last_metrics.token_count == 20
            assert provider.last_metrics.tokens_per_second == 10
            assert health.status == "healthy" and health.model == "fixture-model"
            assert health.device == "cpu"

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["timeout", "unavailable", "malformed_health"])
def test_qwen_health_failures_are_safe(kind):
    def respond(request):
        if kind == "timeout":
            raise httpx.ReadTimeout("sensitive backend detail", request=request)
        if kind == "unavailable":
            raise httpx.ConnectError("sensitive backend detail", request=request)
        return httpx.Response(200, json={"wrong": []})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with pytest.raises(ProviderUnavailableError) as error:
                await QwenProvider(cloud_settings(), client).health_check()
            assert "sensitive" not in str(error.value)
            assert "http://127.0.0.1:11434" in str(error.value)

    asyncio.run(run())


def test_qwen_schema_validation_uses_typed_error():
    async def run():
        transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json={"message": {"content": "not json"}})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderResponseValidationError):
                await QwenProvider(cloud_settings(), client).generate_structured(
                    REQUEST, LiveTurnDecision
                )

    asyncio.run(run())


def test_whisper_cpu_configuration_metadata_and_metrics(monkeypatch):
    calls = []

    class Runtime:
        def __init__(self, model, **kwargs):
            calls.append((model, kwargs))

        def transcribe(self, values, **kwargs):
            calls.append(kwargs)
            return iter([SimpleNamespace(text=" fixture transcript ")]), SimpleNamespace(
                language="en", language_probability=0.98
            )

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Runtime))
    provider = WhisperProvider(cloud_settings())
    transcript = asyncio.run(provider.transcribe(AudioBuffer(b"\x00\x00" * 16000)))
    assert calls[0][0] == "base.en"
    assert calls[0][1]["device"] == "cpu" and calls[0][1]["compute_type"] == "int8"
    assert calls[1]["language"] == "en"
    assert transcript.detected_language == "en" and transcript.realtime_factor is not None
    assert provider.last_metrics.audio_duration_seconds == 1
    with pytest.raises(AudioProcessingError):
        asyncio.run(provider.transcribe(AudioBuffer(b"")))


def test_kokoro_cpu_settings_validation_and_health(monkeypatch, tmp_path):
    asset = tmp_path / "fixture.asset"
    asset.write_text("not model data", encoding="utf-8")
    devices = []

    class Tensor:
        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return np.zeros(2400, dtype=np.float32)

    class Model:
        def __init__(self, **kwargs):
            pass

        def to(self, device):
            devices.append(device)
            return self

        def eval(self):
            return self

    class Pipeline:
        def __init__(self, **kwargs):
            pass

        def __call__(self, text, **kwargs):
            return iter([("", "", Tensor())])

    monkeypatch.setitem(sys.modules, "kokoro", SimpleNamespace(KModel=Model, KPipeline=Pipeline))
    provider = KokoroProvider(
        cloud_settings(
            tts_model_path=asset,
            kokoro_config_path=asset,
            kokoro_voice_path=asset,
            tts_device="cpu",
        )
    )
    health = asyncio.run(provider.health_check())
    audio = asyncio.run(provider.synthesize("Synthetic question?"))
    assert devices == ["cpu"] and health.device == "cpu" and audio.duration == 0.1
    with pytest.raises(AudioProcessingError):
        asyncio.run(provider.synthesize("  "))


def test_silero_cpu_thresholds_segments_and_health(monkeypatch):
    kwargs_seen = []

    class Model:
        def to(self, device):
            assert device == "cpu"
            return self

        def eval(self):
            return self

    def timestamps(values, model, **kwargs):
        kwargs_seen.append(kwargs)
        return [{"start": 0, "end": 8000}]

    monkeypatch.setitem(
        sys.modules,
        "silero_vad",
        SimpleNamespace(load_silero_vad=Model, get_speech_timestamps=timestamps),
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(from_numpy=lambda values: values))
    provider = SileroProvider(
        cloud_settings(vad_threshold=0.6, vad_min_speech_ms=300, vad_min_silence_ms=500)
    )
    health = asyncio.run(provider.health_check())
    result = asyncio.run(provider.detect_end_of_turn(AudioBuffer(b"\x00\x00" * 24000)))
    assert health.device == "cpu" and result.end_of_turn and result.segments == ((0, 0.5),)
    assert kwargs_seen[0]["threshold"] == 0.6
    assert kwargs_seen[0]["min_speech_duration_ms"] == 300
    assert kwargs_seen[0]["min_silence_duration_ms"] == 500


def test_mock_health_and_cpu_metrics_utilities(settings):
    health = asyncio.run(create_providers(settings).health_check())
    assert all(item.status == "healthy" and item.mode == "mock" for item in health.values())
    metrics = ProviderOperationMetrics("transcribe", 1.8, audio_duration_seconds=10)
    assert metrics.realtime_factor == pytest.approx(0.18)
    assert safe_ratio(1, 0) is None


@pytest.mark.parametrize(
    "parse,args,provider",
    [
        (verification_parser, ["--provider", "tts", "--text", "fixture"], "tts"),
        (benchmark_parser, ["--provider", "all", "--audio", "sample.wav"], "all"),
    ],
)
def test_provider_cli_arguments(parse, args, provider):
    parsed: argparse.Namespace = parse().parse_args(args)
    assert parsed.provider == provider
