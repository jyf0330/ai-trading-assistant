#!/usr/bin/env bash
set -euo pipefail

cd /home/ywh/projects/ai-trading-assistant
./scripts/collect-all-snapshots.sh
./scripts/start-app-shell.sh
