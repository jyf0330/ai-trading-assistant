#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/ywh/projects/ai-trading-assistant"
APP_DIR="$ROOT/vendors/journedge"
LOG_FILE="/tmp/journedge.log"

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

if [[ ! -d node_modules ]]; then
  npm install --package-lock=false
fi

npx prisma generate
npx prisma db push

pkill -f "next-server.*journedge" >/dev/null 2>&1 || true
pkill -f "next dev" >/dev/null 2>&1 || true

nohup npm run dev >"$LOG_FILE" 2>&1 &

sleep 5
curl -I --max-time 10 http://127.0.0.1:3000

echo "Journedge started: http://localhost:3000"
echo "Log: $LOG_FILE"