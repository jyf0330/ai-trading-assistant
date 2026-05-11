from __future__ import annotations

import io
import json
import math
import os
import random
import re
import shlex
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import yfinance as yf

from .config import ROOT
from .journedge_export import load_journedge_export

LOCAL_DATA_DIR = ROOT / "data" / "shell"
LOCAL_PAPER_PATH = LOCAL_DATA_DIR / "paper_account.json"
ANALYSIS_RUNS_DIR = ROOT / "data" / "snapshots" / "tradingagents" / "runs"
A_SHARE_PATTERN = re.compile(r"^(\d{6})(?:\.(SH|SZ|BJ))?$", re.IGNORECASE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_RUNS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_symbol(symbol: str) -> str:
    raw = symbol.strip().upper()
    match = A_SHARE_PATTERN.fullmatch(raw)
    if not match:
        return raw
    code, suffix = match.groups()
    if suffix:
        return f"{code}.{suffix}"
    if code.startswith(("5", "6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "1", "2", "3")):
        return f"{code}.SZ"
    return raw


def is_a_share_symbol(symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    return normalized.endswith(".SH") or normalized.endswith(".SZ") or normalized.endswith(".BJ")


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
            normalized = {
                "symbol": data.get("symbol") or data.get("ticker") or path.stem,
                "trade_date": data.get("trade_date") or data.get("date") or "",
                "summary": data.get("summary") or data.get("decision") or "No summary",
                "model": data.get("model"),
                "path": str(path),
            }
            runs.append(normalized)
        except Exception:
            runs.append({"symbol": path.stem, "trade_date": "", "summary": "Failed to parse analysis output", "path": str(path)})
    return runs


def _fetch_akshare_history(symbol: str) -> list[dict[str, Any]]:
    import akshare as ak
    import pandas as pd

    normalized = normalize_symbol(symbol)
    code = normalized.split(".")[0]
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="")
    if df.empty:
        raise ValueError(f"AKShare 未返回 {normalized} 的历史数据")
    date_col = "日期" if "日期" in df.columns else df.columns[0]
    close_col = "收盘" if "收盘" in df.columns else "close"
    df[date_col] = pd.to_datetime(df[date_col])
    return [{"Date": row[date_col].date().isoformat(), "Close": float(row[close_col])} for _, row in df.iterrows()]


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
    seed = sum(ord(ch) for ch in normalize_symbol(symbol))
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
    normalized = normalize_symbol(symbol)
    if is_a_share_symbol(normalized):
        try:
            records = _fetch_akshare_history(normalized)
            if len(records) < 60:
                raise ValueError(f"{normalized} 的历史数据不足，无法计算均线")
            return float(records[-1]["Close"]), records, "akshare"
        except Exception:
            records = _generate_synthetic_history(normalized)
            return float(records[-1]["Close"]), records, "synthetic"

    try:
        history = yf.Ticker(normalized).history(period=period, interval="1d", auto_adjust=False)
        if history.empty or len(history) < 60:
            raise ValueError("not enough yfinance history")
        records = history.reset_index().to_dict(orient="records")
        return float(history["Close"].iloc[-1]), records, "yfinance"
    except Exception:
        try:
            records = _fetch_stooq_history(normalized)
            if len(records) < 60:
                raise ValueError(f"{normalized} 的历史数据不足，无法计算 10/50 均线")
            return float(records[-1]["Close"]), records, "stooq"
        except Exception:
            records = _generate_synthetic_history(normalized)
            return float(records[-1]["Close"]), records, "synthetic"


def compute_ma_signal(symbol: str) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    _, records, source = latest_price(normalized)
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
        "symbol": normalized,
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
    normalized = normalize_symbol(symbol)
    model_name = os.environ.get("TRADINGAGENTS_OLLAMA_MODEL", "gemma4:latest")
    cmd = _build_tradingagents_command(normalized, trade_date)
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
        "symbol": normalized,
        "trade_date": trade_date,
        "summary": summary,
        "model": model_name,
        "result_path": result_path,
    }


def _windows_wsl_project_root() -> str:
    configured = os.environ.get("AI_TRADING_ASSISTANT_WSL_ROOT")
    if configured:
        return configured
    result = subprocess.run(
        ["wsl.exe", "wslpath", "-a", str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Windows 环境下无法解析 WSL 项目路径。请设置 AI_TRADING_ASSISTANT_WSL_ROOT 指向 WSL 中的仓库目录。"
        )
    return result.stdout.strip()


def _build_tradingagents_command(symbol: str, trade_date: str) -> list[str]:
    script_path = ROOT / "scripts" / "run-tradingagents-local.sh"
    if os.name == "nt":
        if not shutil.which("wsl.exe"):
            raise RuntimeError(
                "Windows 环境需要 WSL 才能运行 TradingAgents 分析。请先安装 WSL，或设置可替代的分析入口。"
            )
        wsl_root = _windows_wsl_project_root()
        quoted_root = shlex.quote(wsl_root)
        quoted_symbol = shlex.quote(symbol)
        quoted_date = shlex.quote(trade_date)
        return [
            "wsl.exe",
            "bash",
            "-lc",
            f"cd {quoted_root} && ./scripts/run-tradingagents-local.sh {quoted_symbol} {quoted_date}",
        ]
    if shutil.which("bash"):
        return ["bash", str(script_path), symbol, trade_date]
    return [str(script_path), symbol, trade_date]


def _heuristic_a_share_summary(signal: dict[str, Any]) -> str:
    direction = {
        "golden_cross": "偏多",
        "death_cross": "偏空",
        "hold": "中性",
    }.get(signal["signal"], "中性")
    return (
        f"A股本地分析：{direction}。\n"
        f"标的 {signal['symbol']} 当前价格 {signal['price']}，"
        f"SMA10 为 {signal['sma_fast']}，SMA50 为 {signal['sma_slow']}。\n"
        f"当前信号为 {signal['signal']}，数据来源为 {signal['data_source']}。\n"
        "该结论仅用于本地研究与模拟盘参考，不构成投资建议。"
    )


def _ollama_text_summary(prompt: str, model_name: str = "qwen3.6:35b-a3b-q4_K_M") -> str:
    with httpx.Client(timeout=180.0) as client:
        response = client.post(
            "http://127.0.0.1:11434/v1/chat/completions",
            json={
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是一个谨慎的A股研究助手。"
                            "请用中文输出简短分析，包含：趋势判断、技术面解读、风险提示。"
                            "不要承诺收益，不要给出实盘建议。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 220,
            },
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]["message"]
        content = (choice.get("content") or "").strip()
        reasoning = (choice.get("reasoning") or "").strip()
        return content or reasoning or ""


def run_a_share_analysis(symbol: str, trade_date: str) -> dict[str, Any]:
    _ensure_dirs()
    normalized = normalize_symbol(symbol)
    signal = compute_ma_signal(normalized)
    model_name = "qwen3.6:35b-a3b-q4_K_M"
    prompt = (
        f"请分析A股标的 {normalized}。\n"
        f"分析日期：{trade_date}\n"
        f"当前价格：{signal['price']}\n"
        f"SMA10：{signal['sma_fast']}\n"
        f"SMA50：{signal['sma_slow']}\n"
        f"交叉信号：{signal['signal']}\n"
        f"数据来源：{signal['data_source']}\n"
        "请输出一段简洁中文分析，最后给出 偏多 / 中性 / 偏空 之一。"
    )

    try:
        summary = _ollama_text_summary(prompt, model_name=model_name)
        if not summary:
            raise RuntimeError("empty ollama summary")
    except Exception:
        summary = _heuristic_a_share_summary(signal)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = ANALYSIS_RUNS_DIR / f"{stamp}-{normalized.replace('.', '_')}"
    payload = {
        "ticker": normalized,
        "trade_date": trade_date,
        "model": model_name,
        "decision": summary,
        "data_source": signal["data_source"],
        "signal": signal["signal"],
        "price": signal["price"],
        "sma_fast": signal["sma_fast"],
        "sma_slow": signal["sma_slow"],
    }
    (base.with_suffix(".json")).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (base.with_suffix(".md")).write_text(
        "\n".join(
            [
                "# A-share Local Analysis",
                "",
                f"- ticker: {normalized}",
                f"- trade_date: {trade_date}",
                f"- model: {model_name}",
                f"- data_source: {signal['data_source']}",
                "",
                "## summary",
                "",
                summary,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "symbol": normalized,
        "trade_date": trade_date,
        "summary": summary,
        "model": model_name,
        "result_path": str(base.with_suffix(".json")),
        "data_source": signal["data_source"],
    }




def build_behavior_profile() -> dict[str, Any]:
    export = load_journedge_export()
    account = load_local_paper_account()
    orders = account.get("orders", [])

    symbol_counter = Counter(order.get("symbol", "UNKNOWN") for order in orders)
    action_counter = Counter(order.get("action", "unknown") for order in orders)
    source_counter = Counter(order.get("data_source", "unknown") for order in orders)

    a_share_events = sum(1 for order in orders if is_a_share_symbol(order.get("symbol", "")))
    us_events = sum(1 for order in orders if order.get("symbol") and not is_a_share_symbol(order.get("symbol", "")))

    suggestions: list[str] = []
    if export["summary"]["trade_count"] < 5:
        suggestions.append("真实交易记录样本还少，先继续积累导入/补录数据，再做更有说服力的习惯判断。")
    if orders and action_counter.get("hold", 0) == len(orders):
        suggestions.append("你当前更多是在观察信号而不是执行交易，说明你偏谨慎，适合先把入场规则写得更明确。")
    if source_counter.get("synthetic", 0) > 0:
        suggestions.append("当前部分行为分析仍建立在 synthetic 回退数据上，结论更适合用来练流程，不适合当真实市场结论。")
    if a_share_events > us_events and a_share_events > 0:
        suggestions.append("你最近更关注 A 股标的，后续应优先把 A 股真实数据源稳定下来。")
    if symbol_counter:
        top_symbol, top_count = symbol_counter.most_common(1)[0]
        if top_count >= 2:
            suggestions.append(f"你反复关注 {top_symbol}，说明你有明显的主观察标的习惯，可以围绕它建立固定复盘模板。")
    if not suggestions:
        suggestions.append("当前样本还少，继续积累行为数据后再看更细的习惯偏差。")

    return {
        "generated_at": _now_iso(),
        "journedge_trade_count": export["summary"]["trade_count"],
        "journedge_total_pnl": export["summary"]["total_pnl"],
        "behavior_event_count": len(orders),
        "a_share_event_count": a_share_events,
        "us_event_count": us_events,
        "top_symbols": [
            {"symbol": symbol, "count": count}
            for symbol, count in symbol_counter.most_common(5)
        ],
        "action_breakdown": dict(action_counter),
        "data_source_breakdown": dict(source_counter),
        "suggestions": suggestions,
        "recent_behavior_events": list(reversed(orders))[:20],
    }
