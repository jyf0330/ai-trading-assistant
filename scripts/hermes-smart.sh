#!/usr/bin/env bash
set -euo pipefail

LAN_OLLAMA_URL="${LAN_OLLAMA_URL:-http://192.168.100.41:11434}"
LOCAL_OLLAMA_URL="${LOCAL_OLLAMA_URL:-http://127.0.0.1:11434}"
LAN_MODEL="${LAN_MODEL:-gemma4:latest}"
LOCAL_MODEL="${LOCAL_MODEL:-gemma4:latest}"
BASE_HERMES_HOME="${HERMES_HOME_BASE:-$HOME/.hermes}"
TMP_HERMES_HOME="$(mktemp -d "${TMPDIR:-/tmp}/hermes-home.XXXXXX")"

cleanup() {
  rm -rf "$TMP_HERMES_HOME"
}
trap cleanup EXIT

probe_models() {
  local base_url="$1"
  curl -fsS --max-time 5 "$base_url/v1/models" >/dev/null 2>&1
}

probe_chat() {
  local base_url="$1"
  curl -fsS --max-time 8 \
    -H 'Content-Type: application/json' \
    -d '{"model":"gemma4:latest","messages":[{"role":"user","content":"ping"}],"stream":false}' \
    "$base_url/v1/chat/completions" >/dev/null 2>&1
}

probe_endpoint() {
  local base_url="$1"
  probe_models "$base_url" && probe_chat "$base_url"
}

mkdir -p "$TMP_HERMES_HOME"
if [ -d "$BASE_HERMES_HOME" ]; then
  cp -R "$BASE_HERMES_HOME/." "$TMP_HERMES_HOME/" 2>/dev/null || true
fi
mkdir -p "$TMP_HERMES_HOME"
: > "$TMP_HERMES_HOME/.env"

SELECTED_URL=""
SELECTED_MODEL=""
STATUS_LINE=""

if probe_endpoint "$LAN_OLLAMA_URL"; then
  SELECTED_URL="$LAN_OLLAMA_URL"
  SELECTED_MODEL="$LAN_MODEL"
  STATUS_LINE="Using LAN Ollama: $LAN_OLLAMA_URL"
elif probe_endpoint "$LOCAL_OLLAMA_URL"; then
  SELECTED_URL="$LOCAL_OLLAMA_URL"
  SELECTED_MODEL="$LOCAL_MODEL"
  STATUS_LINE="LAN Ollama unavailable, falling back to local Ollama: $LOCAL_OLLAMA_URL"
elif probe_models "$LAN_OLLAMA_URL"; then
  SELECTED_URL="$LAN_OLLAMA_URL"
  SELECTED_MODEL="$LAN_MODEL"
  STATUS_LINE="LAN Ollama model listing works but chat health probe failed; using LAN anyway: $LAN_OLLAMA_URL"
else
  SELECTED_URL="$LOCAL_OLLAMA_URL"
  SELECTED_MODEL="$LOCAL_MODEL"
  STATUS_LINE="No healthy Ollama endpoint detected; using local config target: $LOCAL_OLLAMA_URL"
fi

cat > "$TMP_HERMES_HOME/config.yaml" <<EOF
model:
  default: "$SELECTED_MODEL"
  provider: "custom"
  base_url: "$SELECTED_URL/v1"
  api_key: "ollama"

providers:
  custom:
    request_timeout_seconds: 300
    stale_timeout_seconds: 600

network:
  force_ipv4: true

terminal:
  backend: "local"
  cwd: "."
  timeout: 180
  lifetime_seconds: 300

toolsets:
  - "hermes-cli"
  - "web"
EOF

echo "$STATUS_LINE"
echo "Hermes home: $TMP_HERMES_HOME"

export HERMES_HOME="$TMP_HERMES_HOME"
export PATH="$HOME/.local/bin:$PATH"
exec hermes "$@"
