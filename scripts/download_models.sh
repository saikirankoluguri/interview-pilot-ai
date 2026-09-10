#!/usr/bin/env bash
# RUN ONLY INSIDE LIGHTNING STUDIO OR THE INTENDED CLOUD RUNTIME.
# This is the only project script that intentionally downloads model assets.
set -euo pipefail

mode="cpu"
provider="all"
confirmed="false"
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --cpu) mode="cpu" ;;
    --gpu) mode="gpu" ;;
    --provider) shift; provider="${1:-}" ;;
    --confirm-cloud-downloads) confirmed="true" ;;
    *) echo "Usage: $0 [--cpu|--gpu] [--provider qwen|whisper|kokoro|silero|all] --confirm-cloud-downloads" >&2; exit 2 ;;
  esac
  shift
done

echo "WARNING: RUN ONLY INSIDE LIGHTNING STUDIO OR THE INTENDED CLOUD RUNTIME."
[[ "$(uname -s)" == "Linux" && "${APP_ENV:-}" == "lightning" ]] || {
  echo "A Linux Lightning runtime with APP_ENV=lightning is required." >&2; exit 1;
}
[[ "$confirmed" == "true" ]] || { echo "Explicit download confirmation is required." >&2; exit 2; }
[[ "$provider" =~ ^(qwen|whisper|kokoro|silero|all)$ ]] || { echo "Unknown provider." >&2; exit 2; }
if [[ "$mode" == "gpu" ]]; then
  command -v nvidia-smi >/dev/null || { echo "GPU mode requires nvidia-smi." >&2; exit 1; }
fi
: "${MODEL_CACHE_DIR:?Set a dedicated absolute persistent model directory}"
[[ "$MODEL_CACHE_DIR" = /* && "$MODEL_CACHE_DIR" != "/" ]] || {
  echo "MODEL_CACHE_DIR must be a dedicated absolute path." >&2; exit 1;
}

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -x .venv/bin/python ]] || { echo "Run the Lightning setup script first." >&2; exit 1; }
export HF_HOME="$MODEL_CACHE_DIR/huggingface"
export HF_HUB_OFFLINE=0
export WHISPER_MODEL_SIZE="${WHISPER_MODEL_SIZE:-base.en}"
export TTS_VOICE="${TTS_VOICE:-af_heart}"

if [[ "$provider" == "qwen" || "$provider" == "all" ]]; then
  : "${LLM_MODEL:?Set the selected Qwen model tag}"
  command -v ollama >/dev/null || { echo "Install Ollama separately first." >&2; exit 1; }
  echo "Downloading configured Qwen tag: $LLM_MODEL"
  ollama pull "$LLM_MODEL"
fi

if [[ "$provider" == "whisper" || "$provider" == "all" ]]; then
  echo "Downloading faster-whisper model: $WHISPER_MODEL_SIZE"
  .venv/bin/python -c 'import os; from faster_whisper.utils import download_model; download_model(os.environ["WHISPER_MODEL_SIZE"], cache_dir=os.environ["MODEL_CACHE_DIR"])'
fi

if [[ "$provider" == "kokoro" || "$provider" == "all" ]]; then
  echo "Downloading configured Kokoro assets and voice: $TTS_VOICE"
  .venv/bin/python - <<'PY'
import os
from pathlib import Path
from huggingface_hub import hf_hub_download

root = Path(os.environ["MODEL_CACHE_DIR"]) / "kokoro"
for filename in ("config.json", "kokoro-v1_0.pth", f"voices/{os.environ['TTS_VOICE']}.pt"):
    hf_hub_download("hexgrad/Kokoro-82M", filename=filename, local_dir=root)
PY
fi

if [[ "$provider" == "silero" || "$provider" == "all" ]]; then
  echo "Silero uses the asset bundled by silero-vad; no torch.hub download is performed."
fi

echo "Requested cloud model preparation completed for mode=$mode provider=$provider."
