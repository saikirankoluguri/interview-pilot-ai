#!/usr/bin/env bash
# LIGHTNING/GPU CLOUD ONLY. NEVER EXECUTE ON THE LOCAL LAPTOP.
set -euo pipefail
echo "LIGHTNING/GPU CLOUD ONLY - explicit model asset downloads"
[[ "$(uname -s)" == "Linux" && "${APP_ENV:-}" == "lightning" ]] || { echo "Run only inside a Linux GPU Studio." >&2; exit 1; }
[[ "${1:-}" == "--confirm-cloud-downloads" ]] || { echo "Pass --confirm-cloud-downloads after checking disk, licenses, and model choices." >&2; exit 2; }
command -v nvidia-smi >/dev/null
nvidia-smi
: "${MODEL_CACHE_DIR:?Set an absolute cloud persistent storage path}"
[[ "$MODEL_CACHE_DIR" = /* && "$MODEL_CACHE_DIR" != "/" ]] || { echo "Use a dedicated absolute model directory." >&2; exit 1; }
: "${LLM_MODEL:?Set the chosen Qwen model tag}"
: "${LLM_BASE_URL:?Set the existing Ollama service URL}"
command -v ollama >/dev/null || { echo "Install and start Ollama separately in the Studio first." >&2; exit 1; }
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export HF_HOME="$MODEL_CACHE_DIR/huggingface"
export HF_HUB_OFFLINE=0
export WHISPER_MODEL_SIZE="${WHISPER_MODEL_SIZE:-small.en}"
export TTS_VOICE="${TTS_VOICE:-af_heart}"
# Ollama must already be running with OLLAMA_MODELS pointing to persistent storage.
OLLAMA_HOST="$LLM_BASE_URL" ollama pull "$LLM_MODEL"
.venv/bin/python - <<'PY'
import os
from pathlib import Path
from faster_whisper.utils import download_model
from huggingface_hub import hf_hub_download
root = Path(os.environ["MODEL_CACHE_DIR"])
download_model(os.environ["WHISPER_MODEL_SIZE"], cache_dir=str(root))
repo = "hexgrad/Kokoro-82M"
for filename in ("config.json", "kokoro-v1_0.pth", f"voices/{os.environ['TTS_VOICE']}.pt"):
    hf_hub_download(repo, filename=filename, local_dir=root / "kokoro")
# Explicitly prepare English phonemizer assets; no interview inference here.
from kokoro import KPipeline
KPipeline(lang_code="a", model=False)
from silero_vad import load_silero_vad
load_silero_vad()  # bundled package model; no torch.hub repository download
print("Cloud assets prepared. Keep ALLOW_MODEL_DOWNLOADS=false for application runs.")
PY
