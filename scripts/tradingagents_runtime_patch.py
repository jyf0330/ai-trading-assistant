from __future__ import annotations

from datetime import datetime, timedelta
import math
import random
from typing import Callable

import pandas as pd
from stockstats import wrap


def apply_runtime_patch() -> None:
    """Patch TradingAgents dataflows so local runs degrade gracefully.

    Yahoo access on this host is unreliable because `yfinance` currently
    depends on `curl_cffi`, which fails TLS handshakes in the local vendor
    environment. These patches keep the analysis pipeline usable by:

    1. Preserving the original implementation when it works.
    2. Falling back to deterministic synthetic OHLCV data for price tools.
    3. Returning explicit "unavailable" reports for live news/fundamentals.
    """

    import tradingagents.dataflows.interface as interface_mod
    import tradingagents.dataflows.stockstats_utils as stockstats_mod
    import tradingagents.dataflows.y_finance as yfinance_mod
    import tradingagents.dataflows.yfinance_news as news_mod

    original_get_stock_data = yfinance_mod.get_YFin_data_online
    original_get_indicators = yfinance_mod.get_stock_stats_indicators_window
    original_get_fundamentals = yfinance_mod.get_fundamentals
    original_get_balance_sheet = yfinance_mod.get_balance_sheet
    original_get_cashflow = yfinance_mod.get_cashflow
    original_get_income_statement = yfinance_mod.get_income_statement
    original_get_insider_transactions = yfinance_mod.get_insider_transactions
    original_get_news = news_mod.get_news_yfinance
    original_get_global_news = news_mod.get_global_news_yfinance
    original_load_ohlcv = stockstats_mod.load_ohlcv

    def _call_or_fallback(func: Callable[[], str], fallback: Callable[[], str]) -> str:
        try:
            result = func()
        except Exception:
            return fallback()
        if isinstance(result, str) and result.lower().startswith("error "):
            return fallback()
        return result

    def _synthetic_ohlcv(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        dates = pd.date_range(start, end, freq="B")
        if len(dates) == 0:
            dates = pd.DatetimeIndex([start.normalize()])

        seed = sum(ord(ch) for ch in symbol.upper())
        rng = random.Random(seed)
        base = 80 + (seed % 120)
        rows: list[dict[str, float | pd.Timestamp]] = []
        prev_close = float(base)

        for idx, current_date in enumerate(dates):
            trend = idx * 0.18
            wave = math.sin(idx / 7.0) * 2.6
            close = max(5.0, base + trend + wave + rng.uniform(-0.9, 0.9))
            open_price = max(5.0, prev_close + rng.uniform(-1.1, 1.1))
            high = max(open_price, close) + abs(rng.uniform(0.2, 1.6))
            low = max(1.0, min(open_price, close) - abs(rng.uniform(0.2, 1.6)))
            volume = int(900_000 + (idx * 3_500) + rng.uniform(-80_000, 80_000))
            rows.append(
                {
                    "Date": current_date,
                    "Open": round(open_price, 2),
                    "High": round(high, 2),
                    "Low": round(low, 2),
                    "Close": round(close, 2),
                    "Adj Close": round(close, 2),
                    "Volume": max(volume, 1),
                }
            )
            prev_close = close

        return pd.DataFrame(rows)

    def _unavailable_report(title: str, symbol: str, detail: str) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return "\n".join(
            [
                f"# {title} for {symbol.upper()}",
                f"# Data retrieved on: {timestamp}",
                "",
                "Live Yahoo Finance data is unavailable in this local environment.",
                detail,
            ]
        )

    def safe_get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
        def fallback() -> str:
            data = _synthetic_ohlcv(symbol, start_date, end_date)
            header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
            header += f"# Total records: {len(data)}\n"
            header += "# Source: synthetic fallback (local runtime patch)\n\n"
            return header + data.to_csv(index=False)

        return _call_or_fallback(
            lambda: original_get_stock_data(symbol, start_date, end_date),
            fallback,
        )

    def safe_load_ohlcv(symbol: str, curr_date: str) -> pd.DataFrame:
        try:
            return original_load_ohlcv(symbol, curr_date)
        except Exception:
            end = min(pd.Timestamp.today().normalize(), pd.Timestamp(curr_date))
            start = end - pd.DateOffset(years=5)
            return _synthetic_ohlcv(
                symbol=symbol,
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
            )

    def safe_get_indicators(symbol: str, indicator: str, curr_date: str, look_back_days: int) -> str:
        def fallback() -> str:
            data = safe_load_ohlcv(symbol, curr_date)
            df = wrap(data.copy())
            df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
            try:
                df[indicator]
            except Exception as exc:
                return (
                    f"## {indicator} values from {curr_date}:\n\n"
                    f"Unable to compute indicator from fallback data: {exc}"
                )

            current = pd.Timestamp(curr_date)
            before = current - pd.DateOffset(days=look_back_days)
            rows = df[(df["Date"] >= before.strftime("%Y-%m-%d")) & (df["Date"] <= current.strftime("%Y-%m-%d"))]
            values = []
            for _, row in rows.iterrows():
                value = row.get(indicator)
                values.append(f"{row['Date']}: {'N/A' if pd.isna(value) else value}")
            header = f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            header += "# Source: synthetic fallback (local runtime patch)\n"
            return header + "\n".join(values)

        return _call_or_fallback(
            lambda: original_get_indicators(symbol, indicator, curr_date, look_back_days),
            fallback,
        )

    def safe_get_fundamentals(ticker: str, curr_date: str | None = None) -> str:
        return _call_or_fallback(
            lambda: original_get_fundamentals(ticker, curr_date),
            lambda: _unavailable_report(
                "Company Fundamentals",
                ticker,
                "Use the price action, technical indicators, and risk discussion with caution because live fundamentals could not be fetched.",
            ),
        )

    def safe_get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
        return _call_or_fallback(
            lambda: original_get_balance_sheet(ticker, freq, curr_date),
            lambda: _unavailable_report("Balance Sheet", ticker, f"Balance sheet data ({freq}) is unavailable from the local fallback."),
        )

    def safe_get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
        return _call_or_fallback(
            lambda: original_get_cashflow(ticker, freq, curr_date),
            lambda: _unavailable_report("Cash Flow", ticker, f"Cash flow data ({freq}) is unavailable from the local fallback."),
        )

    def safe_get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
        return _call_or_fallback(
            lambda: original_get_income_statement(ticker, freq, curr_date),
            lambda: _unavailable_report("Income Statement", ticker, f"Income statement data ({freq}) is unavailable from the local fallback."),
        )

    def safe_get_insider_transactions(ticker: str) -> str:
        return _call_or_fallback(
            lambda: original_get_insider_transactions(ticker),
            lambda: _unavailable_report("Insider Transactions", ticker, "Insider transaction data is unavailable from the local fallback."),
        )

    def safe_get_news(ticker: str, start_date: str, end_date: str) -> str:
        return _call_or_fallback(
            lambda: original_get_news(ticker, start_date, end_date),
            lambda: _unavailable_report(
                "News",
                ticker,
                f"Live ticker news for {start_date} to {end_date} is unavailable from the local fallback.",
            ),
        )

    def safe_get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 10) -> str:
        symbol = "GLOBAL-MARKETS"
        return _call_or_fallback(
            lambda: original_get_global_news(curr_date, look_back_days, limit),
            lambda: _unavailable_report(
                "Global Market News",
                symbol,
                f"Live macro news for the {look_back_days}-day lookback window is unavailable from the local fallback.",
            ),
        )

    stockstats_mod.load_ohlcv = safe_load_ohlcv

    yfinance_mod.get_YFin_data_online = safe_get_stock_data
    yfinance_mod.get_stock_stats_indicators_window = safe_get_indicators
    yfinance_mod.get_fundamentals = safe_get_fundamentals
    yfinance_mod.get_balance_sheet = safe_get_balance_sheet
    yfinance_mod.get_cashflow = safe_get_cashflow
    yfinance_mod.get_income_statement = safe_get_income_statement
    yfinance_mod.get_insider_transactions = safe_get_insider_transactions

    news_mod.get_news_yfinance = safe_get_news
    news_mod.get_global_news_yfinance = safe_get_global_news

    interface_mod.VENDOR_METHODS["get_stock_data"]["yfinance"] = safe_get_stock_data
    interface_mod.VENDOR_METHODS["get_indicators"]["yfinance"] = safe_get_indicators
    interface_mod.VENDOR_METHODS["get_fundamentals"]["yfinance"] = safe_get_fundamentals
    interface_mod.VENDOR_METHODS["get_balance_sheet"]["yfinance"] = safe_get_balance_sheet
    interface_mod.VENDOR_METHODS["get_cashflow"]["yfinance"] = safe_get_cashflow
    interface_mod.VENDOR_METHODS["get_income_statement"]["yfinance"] = safe_get_income_statement
    interface_mod.VENDOR_METHODS["get_news"]["yfinance"] = safe_get_news
    interface_mod.VENDOR_METHODS["get_global_news"]["yfinance"] = safe_get_global_news
    interface_mod.VENDOR_METHODS["get_insider_transactions"]["yfinance"] = safe_get_insider_transactions
