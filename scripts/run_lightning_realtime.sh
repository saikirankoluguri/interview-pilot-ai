#!/usr/bin/env bash
# Start Phase 2 realtime voice on Lightning loopback; never installs or downloads.
set -euo pipefail

[[ "$(uname -s)" == "Linux" ]] || { echo "Linux Lightning Studio required." >&2; exit 1; }
[[ "${APP_ENV:-}" == "lightning" ]] || { echo "Export APP_ENV=lightning first." >&2; exit 1; }
[[ "${REALTIME_TRANSPORT:-}" == "fastrtc" ]] || {
  echo "Set REALTIME_TRANSPORT=fastrtc for the realtime voice loop." >&2; exit 1;
}
for variable in LLM_PROVIDER STT_PROVIDER TTS_PROVIDER VAD_PROVIDER; do
  value="${!variable:-}"
  [[ -n "$value" && "$value" != "mock" ]] || {
    echo "$variable must select its real provider." >&2; exit 1;
  }
done

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -x .venv/bin/python ]] || { echo "Run scripts/setup_lightning_cpu.sh first." >&2; exit 1; }
.venv/bin/python -c 'from importlib.metadata import version; assert version("fastrtc") == "0.0.34"'

host="${SERVER_NAME:-127.0.0.1}"
port="${SERVER_PORT:-7860}"
echo "Realtime transport=$REALTIME_TRANSPORT"
echo "Providers=$LLM_PROVIDER/$STT_PROVIDER/$TTS_PROVIDER/$VAD_PROVIDER"
echo "Devices=${LLM_DEVICE:-cpu}/${WHISPER_DEVICE:-cpu}/${TTS_DEVICE:-cpu}/${VAD_DEVICE:-cpu}"
echo "Listening on $host:$port (use the documented SSH tunnel from Windows)."
export GRADIO_ANALYTICS_ENABLED=False
exec .venv/bin/python -m app.main --host "$host" --port "$port"
