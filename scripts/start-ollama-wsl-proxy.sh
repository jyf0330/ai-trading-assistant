#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
UNAME_S="$(uname -s)"

if [[ "$UNAME_S" != "Linux" ]]; then
  echo "Skipping WSL Ollama proxy on non-Linux host: $UNAME_S"
  exit 0
fi

HOST="${1:-$(ip route | awk '/default/ {print $3}' | head -n 1)}"
PORT="${2:-11434}"

pkill -f "ollama_wsl_proxy.py" >/dev/null 2>&1 || true
nohup python3 "$PROJECT_ROOT/scripts/ollama_wsl_proxy.py" "$HOST" "$PORT" 127.0.0.1 11434 >/tmp/ollama-wsl-proxy.log 2>&1 &
sleep 2
curl --max-time 5 http://127.0.0.1:11434/api/tags >/dev/null

echo "WSL Ollama proxy started: 127.0.0.1:11434 -> $HOST:$PORT"
echo "Log: /tmp/ollama-wsl-proxy.log"
