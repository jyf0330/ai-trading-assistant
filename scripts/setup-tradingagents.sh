#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$ROOT/vendors/tradingagents"

if [[ ! -d "$APP_DIR" ]]; then
  echo "TradingAgents repo not found: $APP_DIR" >&2
  exit 1
fi

cd "$APP_DIR"

if [[ ! -d .venv ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv .venv --python 3.12
  else
    python3 -m venv .venv
  fi
fi

source .venv/bin/activate
if command -v uv >/dev/null 2>&1; then
  uv pip install --python .venv/bin/python -e .
else
  python -m pip install --upgrade pip
  python -m pip install -e .
fi

echo "TradingAgents installed."
echo "Next step:"
echo "  source .venv/bin/activate"
echo "  tradingagents"
echo "Or use the project integration:"
echo "  $ROOT/scripts/run-tradingagents-local.sh NVDA 2026-04-23"
