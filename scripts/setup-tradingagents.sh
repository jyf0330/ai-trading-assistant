#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/ywh/projects/ai-trading-assistant"
APP_DIR="$ROOT/vendors/tradingagents"

cd "$APP_DIR"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .

echo "TradingAgents installed."
echo "Next step:"
echo "  export OPENAI_API_KEY=...   # or another supported provider key"
echo "  source .venv/bin/activate"
echo "  tradingagents"