# InterviewPilot AI

InterviewPilot AI is a voice-first mock interview application. The local V0.1
implementation runs the complete interview workflow with deterministic mock
providers and requires no API key, AI model, or GPU.

**Current status: local implementation complete; Lightning inference unvalidated.**

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
- Voice orchestration from microphone audio through VAD, STT, interview engine,
  TTS, and browser audio. Local mock TTS emits silence and mock STT returns a
  clearly marked deterministic transcript; these are plumbing fixtures.
- A Gradio setup screen, voice-oriented interview screen, and post-interview
  feedback screen. The live screen has no answer textbox, transcript, scores,
  coaching, or ideal answers.
- Lazy Qwen HTTP, faster-whisper, Kokoro, and Silero adapters plus tests using
  mocked HTTP/fake runtimes. Heavy libraries are never imported in mock mode.
- Automated unit/integration tests and a five-turn developer demo.

## Voice-first flow

```text
Browser microphone -> end-of-turn detection -> speech-to-text
      -> one hidden evaluation + adaptive decision + next question
      -> text-to-speech -> browser playback -> repeat
```

Local Gradio audio validates the voice workflow without real recognition or
speech. Lightning uses the optional FastRTC/WebRTC boundary for continuous
send/receive audio. FastRTC 0.0.34 requires Gradio below 6, so the base dependency
range is `gradio>=5.49,<6` until that integration is upgraded and retested.

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
| Lightning | qwen | whisper | kokoro | silero | FastRTC/WebRTC |

Local/test settings reject real providers and reject model downloads. Lightning
requires `APP_ENV=lightning` plus explicit provider selection. See
[the Lightning guide](docs/LIGHTNING_SETUP.md) before cloud work.

## Not yet validated

- Actual Qwen inference or its selected Ollama service/model tag.
- Actual faster-whisper transcription and GPU/CUDA/cuDNN compatibility.
- Actual Kokoro synthesis, voice assets, and language dependencies.
- Actual Silero end-of-turn behavior with live microphone conditions.
- FastRTC/WebRTC behavior through Lightning HTTPS/port routing.
- The 1-4 second end-of-turn latency target on a real GPU.

These tasks require Lightning GPU execution and model assets. No cloud provider,
model, or GPU package is needed or used locally.

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