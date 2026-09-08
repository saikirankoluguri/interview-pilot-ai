#!/usr/bin/env bash
# Start the app only when explicitly run inside Lightning; no setup/download side effects.
set -euo pipefail
[[ "$(uname -s)" == "Linux" && "${APP_ENV:-}" == "lightning" ]] || { echo "Export APP_ENV=lightning in the Studio." >&2; exit 1; }
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -x .venv/bin/python ]] || { echo "Run cloud package setup first." >&2; exit 1; }
export GRADIO_ANALYTICS_ENABLED=False
exec .venv/bin/python -m app.main --host "${SERVER_NAME:-0.0.0.0}" --port "${SERVER_PORT:-7860}"
