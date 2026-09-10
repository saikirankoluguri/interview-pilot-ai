"""Explicit Lightning-only smoke checks for individually configured real providers."""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import Settings
from app.providers.factory import create_providers
from app.providers.llm.base import LLMRequest, LLMTask
from app.utils.errors import ConfigurationError
from app.voice.audio_utils import from_wav_bytes


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--provider", required=True, choices=("llm", "stt", "tts", "vad"))
    result.add_argument("--audio", type=Path, help="Mono PCM WAV for STT or VAD")
    result.add_argument("--text", default="Tell me about your current role.")
    result.add_argument("--health-only", action="store_true")
    return result


def _print(label: str, value: object) -> None:
    print(json.dumps({label: value}, indent=2, default=str))


async def run(args: argparse.Namespace) -> None:
    settings = Settings()
    if settings.app_env != "lightning":
        raise ConfigurationError("Run real-provider verification only with APP_ENV=lightning.")
    configured = {
        "llm": settings.llm_provider,
        "stt": settings.stt_provider,
        "tts": settings.tts_provider,
        "vad": settings.vad_provider,
    }
    if configured[args.provider] == "mock":
        raise ConfigurationError(f"{args.provider.upper()} is still configured as mock.")
    providers = create_providers(settings)
    provider = getattr(providers, args.provider)
    health = await provider.health_check()
    _print("health", health.as_dict())
    if args.health_only:
        return
    if args.provider == "llm":
        await provider.generate(
            LLMRequest(
                task=LLMTask.OPENING,
                instructions="Reply with one short synthetic interview question.",
                context_json="{}",
            )
        )
    elif args.provider in {"stt", "vad"}:
        if args.audio is None:
            raise ConfigurationError("--audio is required for STT and VAD verification.")
        audio = from_wav_bytes(args.audio.read_bytes())
        if args.provider == "stt":
            transcript = await provider.transcribe(audio)
            _print(
                "transcription",
                {
                    "characters": len(transcript.text),
                    "detected_language": transcript.detected_language,
                    "latency_seconds": transcript.latency_seconds,
                    "realtime_factor": transcript.realtime_factor,
                },
            )
        else:
            _print("vad", asdict(await provider.detect_end_of_turn(audio)))
    else:
        audio = await provider.synthesize(args.text)
        _print("tts", {"sample_rate": audio.sample_rate, "duration_seconds": audio.duration})
    metrics = getattr(provider, "last_metrics", None)
    if metrics is not None:
        _print("metrics", asdict(metrics) | {"realtime_factor": metrics.realtime_factor})


def main() -> int:
    try:
        asyncio.run(run(parser().parse_args()))
        return 0
    except Exception as exc:
        print(f"Verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
