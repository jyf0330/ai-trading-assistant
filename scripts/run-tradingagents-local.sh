#!/usr/bin/env bash
set -euo pipefail

TICKER="${1:-AAPL}"
TRADE_DATE="${2:-$(date +%F)}"
MODEL_NAME="${TRADINGAGENTS_OLLAMA_MODEL:-qwen3.6:35b-a3b-q4_K_M}"
RESULT_DIR="/home/ywh/projects/ai-trading-assistant/data/snapshots/tradingagents/runs"
mkdir -p "$RESULT_DIR"

/home/ywh/projects/ai-trading-assistant/scripts/start-ollama-wsl-proxy.sh

cd /home/ywh/projects/ai-trading-assistant/vendors/tradingagents
source .venv/bin/activate
export OPENAI_API_KEY=dummy

PYTHONPATH=. python - <<PY
import json
from datetime import datetime
from pathlib import Path

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config['llm_provider'] = 'ollama'
config['backend_url'] = 'http://127.0.0.1:11434/v1'
config['deep_think_llm'] = '$MODEL_NAME'
config['quick_think_llm'] = '$MODEL_NAME'
config['results_dir'] = '$RESULT_DIR'
config['max_debate_rounds'] = 1
config['max_risk_discuss_rounds'] = 1

ta = TradingAgentsGraph(debug=False, config=config)
_, decision = ta.propagate('$TICKER', '$TRADE_DATE')

stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
base = Path('$RESULT_DIR') / f'{stamp}-$TICKER'
(base.with_suffix('.json')).write_text(
    json.dumps(
        {
            'ticker': '$TICKER',
            'trade_date': '$TRADE_DATE',
            'model': '$MODEL_NAME',
            'decision': decision,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding='utf-8',
)
(base.with_suffix('.md')).write_text(
    f'# TradingAgents Local Run

- ticker: $TICKER
- trade_date: $TRADE_DATE
- model: $MODEL_NAME

## decision

```
{decision}
```
',
    encoding='utf-8',
)
print(base.with_suffix('.json'))
print(decision)
PY
