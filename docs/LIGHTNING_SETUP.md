# Lightning AI Studio CPU setup

This Phase 1 runbook is prepared but has not been executed. Run it only in the
intended Linux Lightning Studio. It installs CPU runtimes and prepares explicit
model operations; it does not install CUDA or change machine type.

## 1. Configure the Studio

Copy `deployment/lightning/lightning.env.example` to an untracked `.env`, update
the persistent paths, and export the values in the shell. The CPU starting point
is intentionally small:

```dotenv
APP_ENV=lightning
LLM_PROVIDER=qwen
STT_PROVIDER=whisper
TTS_PROVIDER=kokoro
VAD_PROVIDER=silero
LLM_DEVICE=cpu
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen2.5:1.5b
WHISPER_MODEL_SIZE=base.en
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
TTS_DEVICE=cpu
VAD_DEVICE=cpu
ALLOW_MODEL_DOWNLOADS=false
```

The exact Qwen tag, Kokoro 0.9.x API/assets, and Silero package behavior must be
verified against packages installed in the Studio. Move to a 3B-class Qwen or
`small.en` Whisper only after measured CPU latency and memory justify it.

## 2. Install CPU packages

Review `requirements-ai-cpu.txt` and then run:

```bash
export APP_ENV=lightning
bash scripts/setup_lightning_cpu.sh
```

The script reports Python, CPU count, and memory; creates/reuses `.venv`; installs
the lightweight base; installs torch/torchaudio from the official CPU wheel index;
installs the AI CPU requirements; and runs `pip check`. It never downloads model
weights. Set `TORCH_CPU_INDEX_URL` only if Lightning requires another verified
official CPU index.

## 3. Prepare persistent model assets explicitly

Set `MODEL_CACHE_DIR` to a dedicated absolute persistent directory. Review model
licenses and available disk, then choose one provider or all:

```bash
bash scripts/download_models.sh --cpu --provider qwen --confirm-cloud-downloads
bash scripts/download_models.sh --cpu --provider whisper --confirm-cloud-downloads
bash scripts/download_models.sh --cpu --provider kokoro --confirm-cloud-downloads
bash scripts/download_models.sh --cpu --provider silero --confirm-cloud-downloads
```

The Qwen step calls an explicit `ollama pull`. Whisper and Kokoro use their
runtime download utilities. Silero reports that `silero-vad` supplies its package
asset and never calls `torch.hub`. None of these commands runs on app startup.

After preparation, set `WHISPER_MODEL_PATH` if using a direct converted-model
directory and confirm `TTS_MODEL_PATH`, `KOKORO_CONFIG_PATH`, and
`KOKORO_VOICE_PATH` point to the cached Kokoro files. Keep
`ALLOW_MODEL_DOWNLOADS=false` for normal operation.

## 4. Start and verify providers

Start the localhost-only inference service in one terminal:

```bash
export QWEN_BIND_ADDRESS=127.0.0.1:11434
bash scripts/start_qwen.sh
```

The script requires an already-installed Ollama and configured `LLM_MODEL`; it
does not pull a model. Then verify providers independently:

```bash
.venv/bin/python scripts/verify_real_providers.py --provider llm
.venv/bin/python scripts/verify_real_providers.py --provider stt --audio sample.wav
.venv/bin/python scripts/verify_real_providers.py --provider tts --text "Tell me about your current role."
.venv/bin/python scripts/verify_real_providers.py --provider vad --audio sample.wav
```

Use `--health-only` to initialize/check a provider without an inference sample.
Health checks are explicit and are never run automatically in local mock mode.

## 5. Measure CPU behavior

Use a synthetic mono 16-bit PCM WAV and do not publish private audio or output:

```bash
.venv/bin/python scripts/benchmark_cpu_providers.py --provider llm
.venv/bin/python scripts/benchmark_cpu_providers.py --provider stt --audio sample.wav
.venv/bin/python scripts/benchmark_cpu_providers.py --provider tts --text "Synthetic question"
.venv/bin/python scripts/benchmark_cpu_providers.py --provider vad --audio sample.wav
.venv/bin/python scripts/benchmark_cpu_providers.py --provider all --audio sample.wav
```

The summary reports available LLM generation metrics, STT realtime factor, TTS
audio duration/generation ratio, and VAD processing duration. Non-streaming
Ollama does not expose time-to-first-response, so that value remains null rather
than being fabricated. No benchmark result is claimed in this repository.

## 6. Run the application

Run regression checks first, then start the application behind Lightning's
restricted HTTPS port:

```bash
.venv/bin/python -m compileall app scripts tests
.venv/bin/ruff check .
.venv/bin/python -m pytest -q -p no:cacheprovider
bash scripts/run_lightning.sh
```

Phase 1 validates programmatic provider swapping and the existing Gradio flow.
FastRTC/WebRTC continuous streaming, browser pause orchestration, barge-in, and
full-duplex voice are explicitly deferred to Phase 2. The retained
`scripts/setup_lightning.sh` and `requirements-gpu.txt` remain available for a
future, separately validated GPU path.
