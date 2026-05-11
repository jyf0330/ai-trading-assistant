#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TICKER="${1:-AAPL}"
TRADE_DATE="${2:-$(date +%F)}"
MODEL_NAME="${TRADINGAGENTS_OLLAMA_MODEL:-gemma4:latest}"
OLLAMA_BASE_URL="${TRADINGAGENTS_OLLAMA_BASE_URL:-${OLLAMA_HOST:-http://127.0.0.1:11434}}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL%/}"
RESULT_DIR="$PROJECT_ROOT/data/snapshots/tradingagents/runs"
mkdir -p "$RESULT_DIR"

if [[ "$OLLAMA_BASE_URL" == "http://127.0.0.1:11434" || "$OLLAMA_BASE_URL" == "http://localhost:11434" ]]; then
  "$PROJECT_ROOT/scripts/start-ollama-wsl-proxy.sh"
fi

cd "$PROJECT_ROOT/vendors/tradingagents"
source .venv/bin/activate
export OPENAI_API_KEY=dummy
export TA_SYMBOL="$TICKER"
export TA_TRADE_DATE="$TRADE_DATE"
export TA_MODEL_NAME="$MODEL_NAME"
export TA_RESULT_DIR="$RESULT_DIR"
export TA_OLLAMA_BASE_URL="$OLLAMA_BASE_URL/v1"

PYTHONPATH="$PROJECT_ROOT/vendors/tradingagents:$PROJECT_ROOT" python - <<'PY'
import json
import os
from datetime import datetime
from pathlib import Path

from scripts.tradingagents_runtime_patch import apply_runtime_patch
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

apply_runtime_patch()

symbol = os.environ['TA_SYMBOL']
trade_date = os.environ['TA_TRADE_DATE']
model_name = os.environ['TA_MODEL_NAME']
result_dir = os.environ['TA_RESULT_DIR']

config = DEFAULT_CONFIG.copy()
config['llm_provider'] = 'ollama'
config['backend_url'] = os.environ['TA_OLLAMA_BASE_URL']
config['deep_think_llm'] = model_name
config['quick_think_llm'] = model_name
config['results_dir'] = result_dir
config['max_debate_rounds'] = 1
config['max_risk_discuss_rounds'] = 1

ta = TradingAgentsGraph(debug=False, config=config)
_, decision = ta.propagate(symbol, trade_date)

stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
base = Path(result_dir) / f'{stamp}-{symbol}'
(base.with_suffix('.json')).write_text(
    json.dumps(
        {
            'ticker': symbol,
            'trade_date': trade_date,
            'model': model_name,
            'decision': decision,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding='utf-8',
)
markdown = "\n".join([
    "# TradingAgents Local Run",
    "",
    f"- ticker: {symbol}",
    f"- trade_date: {trade_date}",
    f"- model: {model_name}",
    "",
    "## decision",
    "",
    "```",
    str(decision),
    "```",
    "",
])
(base.with_suffix('.md')).write_text(markdown, encoding='utf-8')
print(base.with_suffix('.json'))
print(decision)
PY
