# Roadmap

M0-M3 and the local portions of M5-M7 are implemented for deterministic mock
workflow verification. Real provider behavior remains a Lightning-only validation
milestone.

| Milestone | Status |
| --- | --- |
| M0 Repository foundation | Complete locally. |
| M1 Local mock-provider application | Complete; deterministic provider factory and demo. |
| M2 Setup/session engine | Complete; parsing, lifecycle, timer, panel, storage. |
| M3 Voice UI | Complete locally with Gradio audio; FastRTC boundary coded, cloud test pending. |
| M4 Lightning GPU integration | Pending in Lightning only. |
| M5 Real STT/TTS/LLM/VAD | Adapters implemented and mocked in tests; real inference pending. |
| M6 Adaptive interview | Complete locally; validate thresholds with real model output later. |
| M7 Final feedback | Complete locally; real-model quality evaluation pending. |
| M8 Company research | Future; interface/prompt only, no web search. |
| M9 Coding/SQL rounds | Future; no IDE or code/SQL execution. |
| M10 Analytics/history | Future; requires retention and access-control design first. |

The next operational step is to push the reviewed code to a private GitHub
repository, clone it into Lightning, and validate the real GPU providers. Camera,
facial analysis, emotion/personality/honesty detection, RAG, databases, Redis,
Kubernetes, and React remain outside V0.1.