#!/usr/bin/env bash
# LIGHTNING/GPU CLOUD ONLY. This script installs packages, never model weights.
set -euo pipefail
[[ "$(uname -s)" == "Linux" ]] || { echo "Linux cloud environment required." >&2; exit 1; }
[[ "${APP_ENV:-}" == "lightning" ]] || { echo "Export APP_ENV=lightning in the Studio." >&2; exit 1; }
mode="${1:---base}"
[[ "$#" -le 1 && ( "$mode" == "--base" || "$mode" == "--gpu" ) ]] || { echo "Usage: $0 [--base|--gpu]" >&2; exit 2; }
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 -c 'import sys; assert (3, 11) <= sys.version_info[:2] < (3, 14), "Use Python 3.11-3.13; 3.11 recommended for cloud"'
if [[ "$mode" == "--gpu" ]]; then
  command -v nvidia-smi >/dev/null || { echo "GPU runtime is required." >&2; exit 1; }
  nvidia-smi
  : "${TORCH_INDEX_URL:?Set the official PyTorch wheel index matching the Studio GPU runtime}"
fi
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-base.txt
if [[ "$mode" == "--gpu" ]]; then
  .venv/bin/python -m pip install torch torchaudio --index-url "$TORCH_INDEX_URL"
  .venv/bin/python -m pip install -r requirements-gpu.txt
fi
.venv/bin/python -m pip check
echo "Packages ready. Model downloads are a separate explicit cloud step."
