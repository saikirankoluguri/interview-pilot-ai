# Architecture

The application has a deterministic local provider stack and a Phase 2 realtime
voice layer. Real provider inference, browser audio, and CPU latency remain
unvalidated until the documented Lightning run.

```text
Gradio setup / voice interview / feedback
                    |
             application bootstrap
                    |
             InterviewEngine -------- JSON SessionStore
              /      |      \
       planner   live decision  final evaluator
              \      |      /
                  LLMProvider
                    |
 Realtime controller -- STTProvider / TTSProvider / VADProvider
```

## Boundaries

`app/bootstrap.py` is the composition root and the only place that assembles
providers, agents, storage, policy, and engine. The interview domain never checks
for Lightning or imports concrete model libraries.

Providers expose async protocols plus explicit health checks. Mock providers are
deterministic workflow fixtures. Qwen uses an injected/configurable `httpx`
client against Ollama-compatible `/api/chat` and `/api/tags` endpoints and
supports text plus Pydantic-validated JSON-schema output. Whisper, Kokoro,
Silero, Torch, and FastRTC imports occur only inside explicitly selected cloud
adapters or transport creation. Constructors do not load models. Model-backed
providers cache one initialized runtime per application composition and serialize
access with provider-local locks; there is no process-global model state.

Provider failures are classified as unavailable, initialization, inference, or
response-validation errors. Candidate content and audio never enter provider
logs. Operational logs contain provider/model/device, operation, latency, and
success state only. Explicit health results expose status, mode, model/device,
and latency without candidate-facing infrastructure details.

## Interview lifecycle

```text
CREATED -> READY -> IN_PROGRESS -> ENDING -> COMPLETED
    \         \          \            \
     +--------+-----------+-----------> FAILED
                                      |
                                      +-> ENDING -> COMPLETED (recovery report)
```

The session stores UUID identity, timezone-aware timestamps, candidate/settings,
panel, plan, current difficulty, ordered questions/answers, live evaluations,
turn metrics, and final report. Invalid transitions and duplicate answers are
rejected. Server timestamps enforce duration; the UI timer is informational.

Each normal answer uses one structured LLM request returning evaluation, action,
proposed difficulty, and next question. The local adaptive controller is
authoritative: it uses the latest three scores with renormalized 50/30/20 weights,
requires two consistent strong/weak answers, clamps levels to 1-5, and moves at
most one level. Fixed easy/medium/hard sessions remain at levels 2/3/4.
Question routing normalizes fingerprints, prevents exact repeats, limits topic
runs, and corrects provider difficulty proposals.

Live candidate output is an `InterviewMessage` containing only spoken text,
panel identity, and completion status. Hidden evaluation never enters the live UI.
Final evaluation runs after ending and produces feedback for every asked question.

## Realtime voice pipeline

```text
Browser microphone
       |
FastRTC / WebRTC
       |
Realtime bridge (transport conversion and clean WebRTC errors)
       |
RealtimeSessionController <---- per-session lock / playback events
       |
TurnManager -> VADProvider -> bounded candidate AudioBuffer
                              |
                         STTProvider
                              |
                       InterviewEngine
                              |
                   one LiveTurnDecision
                              |
                         TTSProvider
                              |
Realtime bridge -> FastRTC / WebRTC -> browser speakers
```

Audio is normalized as an `AudioBuffer`: mono signed 16-bit little-endian PCM,
explicit sample rate/channel/encoding, and derived duration. Tuple, array, WAV,
and transport conversions stay in `app/voice/audio_utils.py`.

The protected voice states are `IDLE`, `PREPARING`, `INTERVIEWER_SPEAKING`,
`LISTENING`, `CANDIDATE_SPEAKING`, `PROCESSING`, `ENDING`, `COMPLETED`,
and `ERROR`. Microphone chunks are ignored while interviewer audio plays.
Silence can close a turn only after speech has started; pre-speech silence instead
triggers a gentle reminder and, after a larger threshold, an inactivity pause.
Buffers and turn duration are bounded.

Each controller owns its processing and ingestion locks, so one session cannot
submit overlapping STT/LLM/TTS work and does not block other sessions. Completed
turns persist through the engine. A reconnect can attach to the same in-progress
session without generating another question. End requests immediately gate input
and safely finish in-flight work before the closing message/report.

Local mode uses deterministic mock VAD/STT/TTS. The separate, lazy FastRTC adapter
implements a per-connection async send/receive handler for Lightning; transport
code does not own interview decisions. FastRTC 0.0.34 currently constrains Gradio
to `<6`. Browser constraints request echo cancellation, noise suppression, and
automatic gain control, while application gating remains authoritative.

Per-turn metrics timestamp speech end, STT/LLM/TTS start and end, and audio
playback readiness. They derive provider durations, total processing duration,
and speech-end-to-audio-ready duration. These diagnostics are persisted but hidden
from the candidate UI by default.

## Storage and privacy

Uploads receive generated UUID filenames and accept only bounded PDF content.
Path traversal and deletion outside the configured root are rejected. Sessions
and reports use atomic sibling-file replacement. Runtime data is gitignored and
blocked from Gradio file serving. Candidate document content, answer transcripts,
audio, provider payloads, and secrets are not logged.

Resume/JD/answer content is untrusted prompt data. Prompt instructions explicitly
preserve interview rules. V0.1 does not implement authentication; run locally or
behind restricted Lightning access and define retention before using real data.
There is no database, Redis, RAG, camera analysis, or web research.

## Phase 1 Lightning CPU design

```text
Private GitHub -> Lightning CPU checkout -> CPU dependency install
 -> explicit persistent model download -> localhost Qwen service
 -> Qwen/Whisper/Kokoro/Silero verification -> CPU benchmark
```

Model weights live in configured persistent cloud storage and are never imported,
downloaded, or started automatically. `ALLOW_MODEL_DOWNLOADS=false` is the normal
application setting. Cloud scripts require explicit environment and confirmation.
`requirements-ai-cpu.txt` is separate from both lightweight local requirements
and the retained future GPU requirements. It pins the Lightning realtime runtime
to FastRTC 0.0.34 without changing the lightweight local installation.
