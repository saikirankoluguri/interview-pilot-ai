"""Provider tests use injected HTTP transports and fake optional runtimes only."""

import asyncio
import json
import subprocess
import sys
from types import SimpleNamespace

import httpx
import numpy as np
import pytest

from app.config.settings import Settings
from app.providers.factory import create_providers
from app.providers.llm.base import LLMRequest, LLMTask
from app.providers.llm.qwen import QwenProvider
from app.providers.stt.whisper import WhisperProvider
from app.providers.tts.kokoro import KokoroProvider
from app.providers.vad.silero import SileroProvider
from app.schemas.audio import AudioBuffer
from app.schemas.interview import InterviewMessage
from app.utils.errors import ProviderError

REQUEST = LLMRequest(task=LLMTask.OPENING, instructions="Ask one question.", context_json="{}")


def cloud_settings(**overrides):
    return Settings(_env_file=None, app_env="lightning", **overrides)


def test_factory_and_optional_imports(settings):
    bundle = create_providers(settings)
    assert [type(p).__name__ for p in (bundle.llm, bundle.stt, bundle.tts, bundle.vad)] == [
        "MockLLMProvider",
        "MockSTTProvider",
        "MockTTSProvider",
        "MockVADProvider",
    ]
    code = (
        "from app.bootstrap import build_application; import sys; build_application(); "
        "assert not set(['torch','faster_whisper','kokoro','silero_vad','fastrtc']) "
        "& set(sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    bundle = create_providers(
        cloud_settings(
            llm_provider="qwen",
            stt_provider="whisper",
            tts_provider="kokoro",
            vad_provider="silero",
        )
    )
    assert bundle.stt._model is None and bundle.tts._pipeline is None and bundle.vad._model is None


def test_qwen_structured_and_normal():
    async def run():
        requests = []

        def respond(request):
            requests.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "message": {
                        "content": json.dumps(
                            {"question": "Describe a project?", "panel_member": "Morgan"}
                        )
                    }
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            provider = QwenProvider(cloud_settings(llm_model="configured-model"), client)
            response = await provider.generate_structured(REQUEST, InterviewMessage)
            assert response.question == "Describe a project?"
            assert requests[0]["model"] == "configured-model"
            assert requests[0]["stream"] is False and "properties" in requests[0]["format"]
            await provider.generate(REQUEST)
            assert "format" not in requests[1]

    asyncio.run(run())


@pytest.mark.parametrize(
    "failure", ["timeout", "connection", "status", "envelope", "json", "schema"]
)
def test_qwen_errors(failure):
    async def run():
        def respond(request):
            if failure == "timeout":
                raise httpx.ReadTimeout("private backend detail", request=request)
            if failure == "connection":
                raise httpx.ConnectError("private backend detail", request=request)
            if failure == "status":
                return httpx.Response(503, text="private backend detail")
            if failure == "envelope":
                return httpx.Response(200, json={"unexpected": "private detail"})
            return httpx.Response(
                200, json={"message": {"content": "not-json" if failure == "json" else "{}"}}
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with pytest.raises(ProviderError) as error:
                await QwenProvider(cloud_settings(), client).generate_structured(
                    REQUEST, InterviewMessage
                )
            assert "private" not in str(error.value)

    asyncio.run(run())


def test_whisper_lazy_fake_runtime(monkeypatch):
    calls = []

    class Runtime:
        def __init__(self, name, **kwargs):
            calls.append((name, kwargs))

        def transcribe(self, values, **kwargs):
            assert values.dtype == np.float32
            return iter([SimpleNamespace(text=" deterministic fixture ")]), None

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Runtime))
    provider = WhisperProvider(cloud_settings())
    assert not calls
    result = asyncio.run(provider.transcribe(AudioBuffer(b"\x00\x00" * 1600)))
    assert result.text == "deterministic fixture"
    assert calls[0][1]["local_files_only"] is True


def test_kokoro_lazy_fake_runtime(monkeypatch, tmp_path):
    asset = tmp_path / "synthetic.asset"
    asset.write_text("fake runtime fixture, not model weights")
    calls = []

    class Tensor:
        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return np.zeros(2400, dtype=np.float32)

    class Model:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def to(self, device):
            return self

        def eval(self):
            return self

    class Pipeline:
        def __init__(self, **kwargs):
            pass

        def __call__(self, text, **kwargs):
            return iter([("", "", Tensor())])

    monkeypatch.setitem(sys.modules, "kokoro", SimpleNamespace(KModel=Model, KPipeline=Pipeline))
    monkeypatch.setitem(
        sys.modules, "loguru", SimpleNamespace(logger=SimpleNamespace(disable=lambda _: None))
    )
    provider = KokoroProvider(
        cloud_settings(kokoro_model_path=asset, kokoro_config_path=asset, kokoro_voice_path=asset)
    )
    assert not calls
    audio = asyncio.run(provider.synthesize("Example question?"))
    assert audio.sample_rate == 24000 and audio.to_wav().startswith(b"RIFF")


def test_silero_lazy_fake_runtime(monkeypatch):
    calls = []

    def load():
        calls.append("loaded")
        return object()

    def timestamps(values, model, **kwargs):
        return [{"start": 0, "end": 8000}]

    monkeypatch.setitem(
        sys.modules,
        "silero_vad",
        SimpleNamespace(load_silero_vad=load, get_speech_timestamps=timestamps),
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(from_numpy=lambda x: x))
    provider = SileroProvider(cloud_settings())
    assert not calls
    result = asyncio.run(provider.detect_end_of_turn(AudioBuffer(b"\x00\x00" * 24000)))
    assert calls == ["loaded"] and result.speech_detected and result.end_of_turn
