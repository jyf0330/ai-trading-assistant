#!/usr/bin/env bash
set -euo pipefail

cd /home/ywh/projects/ai-trading-assistant/app-shell

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
pkill -f "app-shell-web" >/dev/null 2>&1 || true
pkill -f "app_shell.main" >/dev/null 2>&1 || true
nohup env PYTHONPATH=. python -m app_shell.main >/tmp/app-shell.log 2>&1 &
sleep 5
curl --max-time 10 http://127.0.0.1:8090/ >/dev/null

echo "App shell started: http://localhost:8090"
echo "Log: /tmp/app-shell.log"
