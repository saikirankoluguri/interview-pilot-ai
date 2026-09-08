# Lightning deployment readiness

The local application, provider composition, Qwen HTTP adapter, lazy Whisper,
Kokoro, and Silero adapters, FastRTC handler, and cloud scripts are implemented.
They have not been executed against a Lightning GPU or real model.

Flow: local code -> private GitHub -> Lightning clone -> verified GPU dependencies
-> explicit persistent model downloads -> configure providers -> restricted app
launch -> real voice and latency tests.

Use `lightning.env.example` as an untracked configuration template. Run
`setup_lightning.sh --gpu` only after selecting the correct PyTorch index. Run
`download_models.sh --confirm-cloud-downloads` only after reviewing storage,
licenses, and exact models. Application startup itself never downloads weights.

See [the full runbook](../../docs/LIGHTNING_SETUP.md). Do not install these
requirements or run these scripts on the local laptop.