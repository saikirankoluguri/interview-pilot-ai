# Lightning AI Studio setup

This runbook is prepared but has not been executed. Do not run it on the local
Windows laptop. Real inference requires a Linux Lightning Studio with a compatible
GPU, persistent storage, and restricted HTTPS access.

## Provider configuration

```dotenv
APP_ENV=lightning
LLM_PROVIDER=qwen
STT_PROVIDER=whisper
TTS_PROVIDER=kokoro
VAD_PROVIDER=silero
REALTIME_TRANSPORT=fastrtc
ALLOW_MODEL_DOWNLOADS=false
```

Copy `deployment/lightning/lightning.env.example` to an untracked `.env`, replace
all persistent model paths, and export `APP_ENV=lightning` in the shell because the
scripts do not execute `.env` as shell code.

## Remaining Lightning-only procedure

1. Create a GPU Studio and clone the private GitHub repository.
2. Verify Python 3.11-3.13, GPU driver, CUDA/cuDNN compatibility, disk capacity,
   model licenses, and the current CTranslate2 requirements.
3. Choose the official PyTorch wheel index for that runtime, then run:

   ```bash
   export APP_ENV=lightning
   export TORCH_INDEX_URL=https://download.pytorch.org/whl/REPLACE_WITH_VERIFIED_INDEX
   bash scripts/setup_lightning.sh --gpu
   ```

4. Install/start an Ollama-compatible service manually with its model directory on
   persistent storage. Set `LLM_BASE_URL` and `LLM_MODEL`.
5. Set `MODEL_CACHE_DIR` to a dedicated absolute persistent directory. After
   reviewing licenses, disk usage, and model choices, explicitly run:

   ```bash
   bash scripts/download_models.sh --confirm-cloud-downloads
   ```

6. Verify the downloaded Kokoro paths match `KOKORO_MODEL_PATH`,
   `KOKORO_CONFIG_PATH`, and `KOKORO_VOICE_PATH`. Keep
   `ALLOW_MODEL_DOWNLOADS=false` during normal application runs.
7. Run `bash scripts/run_lightning.sh` behind Lightning's restricted HTTPS port.
8. Test real microphone permission, FastRTC/WebRTC connection, Silero endpointing,
   faster-whisper accuracy, one-call Qwen JSON output, Kokoro playback, interruption,
   timer completion, private feedback, and failure recovery.
9. Measure VAD, STT, live-decision, TTS, and total turn latency. The 1-4 second
   target is not yet validated.

FastRTC 0.0.34 requires `gradio<6`; the base requirements use a compatible range.
The Qwen adapter uses Ollama's HTTP API and never starts or pulls a model. Whisper,
Kokoro, Silero, and FastRTC imports are lazy. Setup and application startup never
download models. Only the separately confirmed download script contains downloads.

No Docker image is required for the first POC. If Docker is used later, mount model
storage at runtime; never bake weights or candidate files into the image.