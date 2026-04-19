#!/usr/bin/env bash
set -euo pipefail

cd /home/ywh/projects/ai-trading-assistant/app-shell

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
app-shell-collect
