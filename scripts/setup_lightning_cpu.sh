#!/usr/bin/env bash
# LIGHTNING CPU STUDIO ONLY. Installs packages, never downloads model weights.
set -euo pipefail

[[ "$(uname -s)" == "Linux" ]] || { echo "Linux Lightning Studio required." >&2; exit 1; }
[[ "${APP_ENV:-}" == "lightning" ]] || { echo "Export APP_ENV=lightning first." >&2; exit 1; }

cd "$(dirname "${BASH_SOURCE[0]}")/.."
echo "Python: $(python3 --version 2>&1)"
echo "CPU count: $(getconf _NPROCESSORS_ONLN 2>/dev/null || echo unknown)"
if [[ -r /proc/meminfo ]]; then
  awk '/MemTotal|MemAvailable/ {printf "%s %.1f GiB\n", $1, $2/1024/1024}' /proc/meminfo
fi
python3 -c 'import sys; assert (3, 11) <= sys.version_info[:2] < (3, 14), "Use Python 3.11-3.13"'

[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-base.txt

torch_cpu_index="${TORCH_CPU_INDEX_URL:-https://download.pytorch.org/whl/cpu}"
.venv/bin/python -m pip install torch torchaudio --index-url "$torch_cpu_index"
.venv/bin/python -m pip install -r requirements-ai-cpu.txt
.venv/bin/python -m pip check

echo "CPU AI packages are ready. No model weights were downloaded by this script."
echo "Review docs/LIGHTNING_SETUP.md before the separate model-download step."
