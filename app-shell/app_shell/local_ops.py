from __future__ import annotations

import io
import json
import math
import random
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import yfinance as yf

from .config import ROOT

LOCAL_DATA_DIR = ROOT / "data" / "shell"
LOCAL_PAPER_PATH = LOCAL_DATA_DIR / "paper_account.json"
ANALYSIS_RUNS_DIR = ROOT / "data" / "snapshots" / "tradingagents" / "runs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_RUNS_DIR.mkdir(parents=True, exist_ok=True)


def load_local_paper_account() -> dict[str, Any]:
    _ensure_dirs()
    if LOCAL_PAPER_PATH.exists():
        return json.loads(LOCAL_PAPER_PATH.read_text(encoding="utf-8"))
    account = {
        "starting_cash": 10000.0,
        "cash": 10000.0,
        "positions": {},
        "orders": [],
        "updated_at": _now_iso(),
    }
    LOCAL_PAPER_PATH.write_text(json.dumps(account, ensure_ascii=False, indent=2), encoding="utf-8")
    return account


def save_local_paper_account(account: dict[str, Any]) -> None:
    _ensure_dirs()
    account["updated_at"] = _now_iso()
    LOCAL_PAPER_PATH.write_text(json.dumps(account, ensure_ascii=False, indent=2), encoding="utf-8")


def list_analysis_runs(limit: int = 10) -> list[dict[str, Any]]:
    _ensure_dirs()
    runs: list[dict[str, Any]] = []
    for path in sorted(ANALYSIS_RUNS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["path"] = str(path)
            runs.append(data)
        except Exception:
            runs.append({"path": str(path), "summary": "Failed to parse analysis output"})
    return runs


def _fetch_stooq_history(symbol: str) -> list[dict[str, Any]]:
    import pandas as pd

    stooq_symbol = f"{symbol.lower()}.us"
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
    if "apikey" in response.text.lower():
        raise ValueError("stooq now requires an api key")
    df = pd.read_csv(io.StringIO(response.text))
    if df.empty or 'Close' not in df.columns:
        raise ValueError(f"无法从 stooq 获取 {symbol} 的历史数据")
    df['Date'] = pd.to_datetime(df['Date'])
    return df.to_dict(orient='records')


def _generate_synthetic_history(symbol: str, days: int = 160) -> list[dict[str, Any]]:
    seed = sum(ord(ch) for ch in symbol.upper())
    rng = random.Random(seed)
    base = 80 + (seed % 120)
    today = datetime.now(timezone.utc)
    records = []
    for idx in range(days):
        date = today - timedelta(days=days - idx)
        trend = idx * 0.12
        wave = math.sin(idx / 8) * 3.5
        noise = rng.uniform(-1.2, 1.2)
        close = round(max(5, base + trend + wave + noise), 4)
        records.append({"Date": date.date().isoformat(), "Close": close})
    return records


def latest_price(symbol: str, period: str = "6mo") -> tuple[float, list[dict[str, Any]], str]:
    try:
        history = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False)
        if history.empty or len(history) < 60:
            raise ValueError("not enough yfinance history")
        records = history.reset_index().to_dict(orient="records")
        return float(history["Close"].iloc[-1]), records, "yfinance"
    except Exception:
        try:
            records = _fetch_stooq_history(symbol)
            if len(records) < 60:
                raise ValueError(f"{symbol} 的历史数据不足，无法计算 10/50 均线")
            return float(records[-1]["Close"]), records, "stooq"
        except Exception:
            records = _generate_synthetic_history(symbol)
            return float(records[-1]["Close"]), records, "synthetic"


def compute_ma_signal(symbol: str) -> dict[str, Any]:
    _, records, source = latest_price(symbol)
    import pandas as pd

    df = pd.DataFrame(records)
    df["sma_fast"] = df["Close"].rolling(window=10).mean()
    df["sma_slow"] = df["Close"].rolling(window=50).mean()
    prev = df.iloc[-2]
    curr = df.iloc[-1]

    signal = "hold"
    if prev["sma_fast"] <= prev["sma_slow"] and curr["sma_fast"] > curr["sma_slow"]:
        signal = "golden_cross"
    elif prev["sma_fast"] >= prev["sma_slow"] and curr["sma_fast"] < curr["sma_slow"]:
        signal = "death_cross"

    return {
        "symbol": symbol.upper(),
        "signal": signal,
        "price": round(float(curr["Close"]), 4),
        "sma_fast": round(float(curr["sma_fast"]), 4),
        "sma_slow": round(float(curr["sma_slow"]), 4),
        "date": str(curr.get("Date", _now_iso())),
        "data_source": source,
    }


def local_paper_summary(account: dict[str, Any]) -> dict[str, Any]:
    positions = account.get("positions", {})
    market_value = 0.0
    position_rows = []
    for symbol, position in positions.items():
        try:
            price, _, source = latest_price(symbol, period="3mo")
        except Exception:
            price = float(position["avg_price"])
            source = "stored"
        qty = float(position["quantity"])
        mv = qty * price
        market_value += mv
        position_rows.append(
            {
                "symbol": symbol,
                "quantity": int(qty),
                "avg_price": float(position["avg_price"]),
                "last_price": round(price, 4),
                "market_value": round(mv, 4),
                "opened_at": position.get("opened_at"),
                "price_source": source,
            }
        )
    equity = float(account["cash"]) + market_value
    pnl = equity - float(account["starting_cash"])
    return {
        "cash": round(float(account["cash"]), 4),
        "starting_cash": round(float(account["starting_cash"]), 4),
        "market_value": round(market_value, 4),
        "equity": round(equity, 4),
        "pnl": round(pnl, 4),
        "positions_count": len(position_rows),
        "positions": position_rows,
        "orders": list(reversed(account.get("orders", [])))[:20],
        "updated_at": account.get("updated_at"),
    }


def run_ma_strategy(symbol: str, allocation: float = 1000.0) -> dict[str, Any]:
    signal = compute_ma_signal(symbol)
    account = load_local_paper_account()
    positions = account.setdefault("positions", {})
    symbol_key = signal["symbol"]
    current_position = positions.get(symbol_key)

    action = "hold"
    quantity = 0
    message = f"{symbol_key} 当前没有新交叉信号，保持不动。"

    if signal["signal"] == "golden_cross" and current_position is None:
        quantity = max(1, int(allocation // signal["price"]))
        cost = quantity * signal["price"]
        if cost <= float(account["cash"]):
            account["cash"] = round(float(account["cash"]) - cost, 4)
            positions[symbol_key] = {
                "quantity": quantity,
                "avg_price": signal["price"],
                "opened_at": _now_iso(),
            }
            action = "buy"
            message = f"Executed buy for {symbol_key}"
        else:
            action = "skip_no_cash"
            message = f"{symbol_key} 出现买入信号，但现金不足。"
    elif signal["signal"] == "death_cross" and current_position is not None:
        quantity = int(current_position["quantity"])
        proceeds = quantity * signal["price"]
        account["cash"] = round(float(account["cash"]) + proceeds, 4)
        positions.pop(symbol_key, None)
        action = "sell"
        message = f"Executed sell for {symbol_key}"

    order = {
        "timestamp": _now_iso(),
        "symbol": symbol_key,
        "signal": signal["signal"],
        "action": action,
        "price": signal["price"],
        "quantity": quantity,
        "allocation": allocation,
        "message": message,
        "data_source": signal["data_source"],
    }
    account.setdefault("orders", []).append(order)
    save_local_paper_account(account)
    return {**signal, **order, "summary": local_paper_summary(account)}


def run_tradingagents_analysis(symbol: str, trade_date: str) -> dict[str, Any]:
    _ensure_dirs()
    cmd = [
        "/home/ywh/projects/ai-trading-assistant/scripts/run-tradingagents-local.sh",
        symbol.upper(),
        trade_date,
    ]
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    stdout_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "TradingAgents local run failed")

    result_path = stdout_lines[0] if stdout_lines else ""
    summary = "\n".join(stdout_lines[1:]).strip() or "TradingAgents run completed."
    return {
        "symbol": symbol.upper(),
        "trade_date": trade_date,
        "summary": summary,
        "model": "qwen3.6:35b-a3b-q4_K_M",
        "result_path": result_path,
    }
