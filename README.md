# InterviewPilot AI

InterviewPilot AI is a voice-first mock interview application. The local V0.1
implementation runs the complete interview workflow with deterministic mock
providers and requires no API key, AI model, or GPU.

**Current status: Phase 2 realtime voice architecture is implemented and locally
verified with deterministic mocks. Real browser audio and AI providers remain
intentionally unvalidated until the Lightning CPU run.**

## Implemented locally

- Validated environment settings with safe mock defaults and a provider factory.
- Typed candidate, interview, panel, question, answer, evaluation, report, audio,
  latency, and session models.
- PDF resume extraction and job-description validation performed only on the local
  machine, with upload size/page limits and no OCR or external upload.
- Protected session transitions, server-side 30/60-minute timing, and early ending.
- Deterministic interview planning, one-call live decision flow, rolling adaptive
  difficulty, duplicate-question protection, final evaluation, and feedback.
- Atomic JSON session/report persistence and safe generated PDF upload filenames.
- A protected realtime state machine, bounded candidate-audio buffer, automatic
  speech start/end handling, interviewer-playback microphone gating, no-speech
  recovery, per-session synchronization, reconnect foundation, and cleanup.
- A lazy FastRTC 0.0.34/WebRTC bridge beneath the Gradio interview screen, with
  echo cancellation, noise suppression, automatic gain control, and clean
  connection/audio status. The original Gradio transport remains the safe local
  fallback when FastRTC is not installed.
- Voice orchestration from microphone chunks through the configured VAD, STT,
  one-call live decision, TTS, and browser playback. Per-turn latency records
  cover speech end through playback readiness.
- A Gradio setup screen, voice-oriented interview screen, and post-interview
  feedback screen. The live screen has no answer textbox, transcript, scores,
  coaching, or ideal answers.
- Complete lazy Qwen HTTP, faster-whisper, Kokoro, and Silero provider paths,
  typed health/errors, latency instrumentation, and tests using mocked HTTP/fake
  runtimes. Heavy libraries are never imported in mock mode.
- Automated unit/integration tests, the original five-turn engine demo, and a
  deterministic three-turn realtime voice demo.

## Voice-first flow

```text
Browser microphone -> end-of-turn detection -> speech-to-text
      -> one hidden evaluation + adaptive decision + next question
      -> text-to-speech -> browser playback -> repeat
```

Local mocks validate the automatic voice lifecycle without recognition, speech,
microphone hardware, or a network. Advanced barge-in is deliberately deferred;
the transport/controller boundary provides the extension point without allowing
interviewer output to be transcribed as a candidate answer.

## Why provider abstraction?

The engine receives LLM, STT, TTS, and VAD protocols through dependency
injection. Logical agents own interview behavior; providers own model and
infrastructure integration. Switching from mock providers to Qwen,
faster-whisper, Kokoro, and Silero therefore happens in the composition root,
without changing interview-domain code.

## Run locally on Windows

Python 3.11-3.13 is supported. From this repository root:

```powershell
./scripts/setup_local.ps1
# Optional: Copy-Item .env.example .env
./.venv/Scripts/python.exe -m app.main
```

The app opens at `http://127.0.0.1:7860`. Local defaults are mock/mock/mock/mock,
analytics are disabled, sharing is disabled, runtime data paths are blocked from
Gradio file serving, and no API key is required.

Useful verification commands:

```powershell
./.venv/Scripts/python.exe -m app.main --check
./.venv/Scripts/python.exe scripts/demo_mock_interview.py
./.venv/Scripts/python.exe scripts/demo_realtime_mock.py
./.venv/Scripts/python.exe -m pytest -p no:cacheprovider
./.venv/Scripts/ruff.exe check .
./.venv/Scripts/ruff.exe format --check .
```

The mock demo uses temporary synthetic data by default and clearly labels its
scores/report as workflow fixtures, not an assessment of a candidate.

## Configuration

| Environment | LLM | STT | TTS | VAD | Realtime transport |
| --- | --- | --- | --- | --- | --- |
| Local/test | mock | mock | mock | mock | Gradio audio |
| Lightning CPU | qwen | whisper | kokoro | silero | FastRTC/WebRTC (Phase 2) |

Local/test settings reject real providers and reject model downloads. Lightning
requires `APP_ENV=lightning` plus explicit provider selection. The CPU starting
point is Qwen 1.5B-class, faster-whisper `base.en` on CPU/int8, Kokoro on CPU, and
Silero on CPU. These are environment-driven choices, not hardcoded production
decisions. See [the Lightning guide](docs/LIGHTNING_SETUP.md) before cloud work.

Phase 1 provider settings include `LLM_DEVICE`, `LLM_MODEL`, `LLM_BASE_URL`,
`LLM_TIMEOUT_SECONDS`, `LLM_TEMPERATURE`, `LLM_MAX_OUTPUT_TOKENS`,
`WHISPER_MODEL_SIZE`, optional `WHISPER_MODEL_PATH`, `WHISPER_DEVICE`,
`WHISPER_COMPUTE_TYPE`, `WHISPER_LANGUAGE`, `TTS_DEVICE`, `TTS_VOICE`,
`TTS_SPEED`, optional `TTS_MODEL_PATH`, `VAD_DEVICE`, optional `VAD_MODEL_PATH`,
`VAD_THRESHOLD`, `VAD_MIN_SPEECH_MS`, `VAD_MIN_SILENCE_MS`, and
`PROVIDER_HEALTHCHECK_ENABLED`. Phase 2 adds `VAD_SPEECH_PAD_MS`,
`MAX_CANDIDATE_TURN_SECONDS`, `NO_SPEECH_TIMEOUT_SECONDS`,
`NO_SPEECH_END_SECONDS`, `REALTIME_VAD_INTERVAL_MS`, and
`REALTIME_MIN_TRANSCRIPT_CHARACTERS`. Safe values are shown in `.env.example`.

## Lightning CPU Phase 2

After cloning in a Linux CPU Studio and reviewing the scripts:

```bash
export APP_ENV=lightning
bash scripts/setup_lightning_cpu.sh
# Separately and explicitly prepare only the selected model assets:
bash scripts/download_models.sh --cpu --provider all --confirm-cloud-downloads
bash scripts/start_qwen.sh
python scripts/verify_real_providers.py --provider llm
python scripts/verify_real_providers.py --provider stt --audio sample.wav
python scripts/benchmark_cpu_providers.py --provider all --audio sample.wav
# After provider checks and realtime environment configuration:
bash scripts/run_lightning_realtime.sh
```

Package setup, model download, service start, verification, and benchmarking are
separate operations. None runs during application import or startup.

## Not yet validated

- Actual Qwen inference or its selected Ollama service/model tag.
- Actual faster-whisper CPU/int8 transcription and model cache compatibility.
- Actual Kokoro synthesis, voice assets, and language dependencies.
- Actual Silero end-of-turn behavior with live microphone conditions.
- CPU latency and memory results for the selected Qwen/Whisper/Kokoro/Silero assets.
- Real FastRTC/WebRTC browser microphone and speaker behavior.
- Realtime Silero speech boundaries, Whisper transcription, Qwen live decisions,
  and Kokoro audio playback together in a live session.
- End-to-end speech-end-to-playback latency on the Lightning CPU.
- Advanced candidate barge-in, which is Phase 3 work.

These tasks require Lightning execution and model assets. No cloud provider,
model, or AI runtime package is needed or used locally.

## Privacy

Never commit resumes, recordings, transcripts, reports, `.env`, credentials, or
model weights. Runtime folders are ignored and Docker excludes all private data
and weights. Logs contain session IDs, state changes, turn numbers, provider
names, and timings; they do not contain resume/JD text, transcripts, audio, or
secrets. Use synthetic test fixtures. V0.1 has no email or phone fields, camera,
facial analysis, emotion/personality/honesty detection, RAG, or web research.

See [architecture](docs/ARCHITECTURE.md), [development](docs/DEVELOPMENT.md),
[interview flow](docs/INTERVIEW_FLOW.md), and [roadmap](docs/ROADMAP.md).
Licensed under the [MIT License](LICENSE).
