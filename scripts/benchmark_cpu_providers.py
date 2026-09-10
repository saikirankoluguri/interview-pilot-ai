"""Measure configured real providers in Lightning CPU without invented results."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import Settings
from app.providers.factory import create_providers
from app.providers.llm.base import LLMRequest, LLMTask
from app.utils.errors import ConfigurationError
from app.voice.audio_utils import from_wav_bytes


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--provider", required=True, choices=("llm", "stt", "tts", "vad", "all"))
    result.add_argument("--audio", type=Path, help="Mono PCM WAV for STT/VAD benchmarks")
    result.add_argument("--text", default="Tell me about your current role.")
    return result


def _metrics(provider: object) -> dict[str, object]:
    value = provider.last_metrics
    return {
        "duration_seconds": value.duration_seconds,
        "audio_duration_seconds": value.audio_duration_seconds,
        "realtime_factor": value.realtime_factor,
        "tokens_generated": value.token_count,
        "tokens_per_second": value.tokens_per_second,
        "time_to_first_response_seconds": value.time_to_first_response_seconds,
    }


async def run(args: argparse.Namespace) -> dict[str, object]:
    settings = Settings()
    if settings.app_env != "lightning":
        raise ConfigurationError("Run CPU benchmarks only with APP_ENV=lightning.")
    selected = ("llm", "stt", "tts", "vad") if args.provider == "all" else (args.provider,)
    configured = {
        "llm": settings.llm_provider,
        "stt": settings.stt_provider,
        "tts": settings.tts_provider,
        "vad": settings.vad_provider,
    }
    if any(configured[name] == "mock" for name in selected):
        raise ConfigurationError("Every benchmarked provider must be configured as real.")
    if any(name in {"stt", "vad"} for name in selected) and args.audio is None:
        raise ConfigurationError("--audio is required when benchmarking STT or VAD.")

    providers = create_providers(settings)
    audio = from_wav_bytes(args.audio.read_bytes()) if args.audio else None
    summary: dict[str, object] = {}
    for name in selected:
        provider = getattr(providers, name)
        await provider.health_check()
        if name == "llm":
            await provider.generate(
                LLMRequest(
                    task=LLMTask.OPENING,
                    instructions="Reply with one short synthetic interview question.",
                    context_json="{}",
                )
            )
            summary[name] = _metrics(provider)
        elif name == "stt":
            await provider.transcribe(audio)
            summary[name] = _metrics(provider)
        elif name == "tts":
            generated = await provider.synthesize(args.text)
            values = _metrics(provider)
            values.update(
                {
                    "text_characters": len(args.text),
                    "generated_audio_seconds": generated.duration,
                    "generation_ratio": provider.last_metrics.generation_ratio,
                }
            )
            summary[name] = values
        else:
            await provider.detect_end_of_turn(audio)
            summary[name] = _metrics(provider)
    return summary


def main() -> int:
    try:
        print(json.dumps(asyncio.run(run(parser().parse_args())), indent=2, default=str))
        return 0
    except Exception as exc:
        print(f"Benchmark failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
