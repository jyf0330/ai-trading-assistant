import os
from pathlib import Path

ROOT = Path(os.environ.get("AI_TRADING_ASSISTANT_ROOT", Path(__file__).resolve().parents[2]))
VENDORS_DIR = ROOT / "vendors"
SNAPSHOTS_DIR = ROOT / "data" / "snapshots"

VENDOR_NAMES = [
    "journedge",
    "tradingagents",
    "open-paper-trading-mcp",
    "vectorbt-lab",
]

VENDOR_PATHS = {name: VENDORS_DIR / name for name in VENDOR_NAMES}
SNAPSHOT_PATHS = {name: SNAPSHOTS_DIR / name for name in VENDOR_NAMES}
