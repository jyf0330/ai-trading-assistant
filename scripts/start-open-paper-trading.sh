#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/ywh/projects/ai-trading-assistant"
APP_DIR="$ROOT/vendors/open-paper-trading-mcp"
FASTAPI_LOG="/tmp/open-paper-fastapi.log"
MCP_LOG="/tmp/open-paper-mcp.log"

cd "$APP_DIR"

docker compose up -d db

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

python3 - <<'PY'
from pathlib import Path

p = Path(".env")
text = p.read_text() if p.exists() else ""
updates = {
    "DATABASE_URL": "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db",
    "QUOTE_ADAPTER_TYPE": "test",
    "TEST_SCENARIO": "ui_testing",
    "TEST_DATE": "2025-07-30",
    "MCP_SERVER_HOST": "0.0.0.0",
    "MCP_HTTP_URL": "http://localhost:2081",
}

lines = [
    line
    for line in text.splitlines()
    if line and not any(line.startswith(k + "=") for k in updates)
]

for key, value in updates.items():
    if any(ch in value for ch in " #"):
        lines.append(f'{key}="{value}"')
    else:
        lines.append(f"{key}={value}")

p.write_text("\n".join(lines) + "\n")
PY

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip

python - <<'PY' > /tmp/open-paper-trading-deps.txt
import tomllib
from pathlib import Path

obj = tomllib.loads(Path("pyproject.toml").read_text())
for dep in obj["project"]["urls"]["dependencies"]:
    print(dep)
PY

python -m pip install -r /tmp/open-paper-trading-deps.txt
python -m pip install "pydantic<2.12" "pydantic-settings<2.12"

python - <<'PY'
import asyncio
from app.storage.database import init_db

asyncio.run(init_db())
PY

pkill -f "app.main" >/dev/null 2>&1 || true
pkill -f "app.mcp_server" >/dev/null 2>&1 || true

nohup env PYTHONPATH=. python -m app.main >"$FASTAPI_LOG" 2>&1 &
nohup env PYTHONPATH=. python -m app.mcp_server >"$MCP_LOG" 2>&1 &

sleep 8
curl --max-time 10 http://127.0.0.1:2080/health
curl --max-time 10 http://127.0.0.1:2080/api/v1/trading/health
curl --max-time 10 http://127.0.0.1:2081/ >/dev/null

echo
echo "Open Paper Trading FastAPI: http://localhost:2080"
echo "Open Paper Trading Docs: http://localhost:2080/docs"
echo "Open Paper Trading MCP: http://localhost:2081"
echo "FastAPI log: $FASTAPI_LOG"
echo "MCP log: $MCP_LOG"