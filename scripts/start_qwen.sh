#!/usr/bin/env bash
# Starts an already-installed Ollama-compatible service; never pulls a model.
set -euo pipefail

[[ "$(uname -s)" == "Linux" ]] || { echo "Linux runtime required." >&2; exit 1; }
[[ "${APP_ENV:-}" == "lightning" ]] || { echo "Export APP_ENV=lightning first." >&2; exit 1; }
: "${LLM_MODEL:?Set LLM_MODEL to an already-downloaded Qwen model tag}"
command -v ollama >/dev/null || { echo "Install Ollama in the Studio first." >&2; exit 1; }

bind_address="${QWEN_BIND_ADDRESS:-127.0.0.1:11434}"
case "$bind_address" in
  127.0.0.1:*|localhost:*) ;;
  *) echo "QWEN_BIND_ADDRESS must bind to localhost only." >&2; exit 1 ;;
esac

echo "Starting local Qwen service for configured model tag: $LLM_MODEL"
echo "This command does not pull a model."
export OLLAMA_HOST="$bind_address"
exec ollama serve
