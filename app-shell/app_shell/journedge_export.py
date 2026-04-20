from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT

JOURNEDGE_DB_PATH = ROOT / "vendors" / "journedge" / "prisma" / "prisma" / "journedge.db"
EXPORT_DIR = ROOT / "data" / "exports" / "journedge"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def load_journedge_export(db_path: Path | None = None) -> dict[str, Any]:
    db_path = db_path or JOURNEDGE_DB_PATH
    payload: dict[str, Any] = {
        "generated_at": now_iso(),
        "db_path": str(db_path),
        "exists": db_path.exists(),
        "accounts": [],
        "tags": [],
        "recent_trades": [],
        "summary": {
            "trade_count": 0,
            "account_count": 0,
            "tag_count": 0,
            "total_pnl": 0.0,
            "win_count": 0,
            "loss_count": 0,
            "symbol_pnl": [],
            "tag_frequency": [],
        },
    }
    if not db_path.exists():
        return payload

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    accounts = [
        dict(row)
        for row in cur.execute(
            "SELECT id, name, broker, initialBalance, currency, createdAt FROM Account ORDER BY datetime(createdAt) DESC"
        ).fetchall()
    ]
    tags = [dict(row) for row in cur.execute("SELECT id, name FROM Tag ORDER BY name").fetchall()]
    trades = [
        dict(row)
        for row in cur.execute(
            "SELECT id, date, symbol, underlying, type, direction, quantity, entryPrice, exitPrice, pnl, status, tags, journalEntry, accountId, createdAt FROM Trade ORDER BY datetime(createdAt) DESC"
        ).fetchall()
    ]

    tag_counter: Counter[str] = Counter()
    symbol_pnl: defaultdict[str, float] = defaultdict(float)
    win_count = 0
    loss_count = 0
    total_pnl = 0.0
    normalized_trades = []
    for trade in trades:
        tags_list = _json_loads(trade.get("tags"), [])
        trade["tags_list"] = tags_list
        normalized_trades.append(trade)
        for tag in tags_list:
            tag_counter[tag] += 1
        symbol_pnl[trade["symbol"]] += float(trade.get("pnl") or 0)
        total_pnl += float(trade.get("pnl") or 0)
        if trade.get("status") == "WIN":
            win_count += 1
        elif trade.get("status") == "LOSS":
            loss_count += 1

    payload["accounts"] = accounts
    payload["tags"] = tags
    payload["recent_trades"] = normalized_trades[:50]
    payload["summary"] = {
        "trade_count": len(normalized_trades),
        "account_count": len(accounts),
        "tag_count": len(tags),
        "total_pnl": round(total_pnl, 4),
        "win_count": win_count,
        "loss_count": loss_count,
        "symbol_pnl": [
            {"symbol": symbol, "pnl": round(pnl, 4)}
            for symbol, pnl in sorted(symbol_pnl.items(), key=lambda item: item[1], reverse=True)
        ],
        "tag_frequency": [
            {"name": tag, "count": count}
            for tag, count in tag_counter.most_common()
        ],
    }
    conn.close()
    return payload


def render_journedge_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Journedge Local Export",
        "",
        f"- Generated: {payload.get('generated_at')}",
        f"- Database: {payload.get('db_path')}",
        f"- Trade count: {payload['summary']['trade_count']}",
        f"- Account count: {payload['summary']['account_count']}",
        f"- Total PnL: {payload['summary']['total_pnl']}",
        "",
        "## Accounts",
    ]
    if payload["accounts"]:
        for account in payload["accounts"]:
            lines.append(f"- {account['name']} | {account['broker']} | {account['initialBalance']} {account['currency']}")
    else:
        lines.append("- No accounts")

    lines.extend(["", "## Tag Frequency"])
    if payload["summary"]["tag_frequency"]:
        for item in payload["summary"]["tag_frequency"]:
            lines.append(f"- {item['name']}: {item['count']}")
    else:
        lines.append("- No tags")

    lines.extend(["", "## Recent Trades"])
    if payload["recent_trades"]:
        for trade in payload["recent_trades"][:20]:
            tags = ", ".join(trade.get("tags_list", [])) or "-"
            lines.append(
                f"- {trade['date']} | {trade['symbol']} | {trade['direction']} | qty {trade['quantity']} | pnl {trade['pnl']} | {trade['status']} | tags: {tags}"
            )
    else:
        lines.append("- No trades")

    return "\n".join(lines) + "\n"


def export_journedge_files(output_dir: Path | None = None, db_path: Path | None = None) -> tuple[Path, Path, dict[str, Any]]:
    payload = load_journedge_export(db_path)
    markdown = render_journedge_markdown(payload)
    output_dir = output_dir or EXPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "latest.json"
    md_path = output_dir / "latest.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return json_path, md_path, payload


def main() -> None:
    json_path, md_path, payload = export_journedge_files()
    print(json_path)
    print(md_path)
    print(json.dumps({"trade_count": payload["summary"]["trade_count"], "account_count": payload["summary"]["account_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
