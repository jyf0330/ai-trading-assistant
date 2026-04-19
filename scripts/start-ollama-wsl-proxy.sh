#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-$(ip route | awk '/default/ {print $3}' | head -n 1)}"
PORT="${2:-11434}"

pkill -f "ollama_wsl_proxy.py" >/dev/null 2>&1 || true
nohup python3 /home/ywh/projects/ai-trading-assistant/scripts/ollama_wsl_proxy.py "$HOST" "$PORT" 127.0.0.1 11434 >/tmp/ollama-wsl-proxy.log 2>&1 &
sleep 2
curl --max-time 5 http://127.0.0.1:11434/api/tags >/dev/null

echo "WSL Ollama proxy started: 127.0.0.1:11434 -> $HOST:$PORT"
echo "Log: /tmp/ollama-wsl-proxy.log"
