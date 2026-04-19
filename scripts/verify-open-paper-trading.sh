#!/usr/bin/env bash
set -euo pipefail

base="http://127.0.0.1:2080/api/v1/trading"

curl -fsS http://127.0.0.1:2080/health >/dev/null
echo "health ok"

curl -fsS "$base/accounts" >/dev/null
echo "accounts ok"

curl -fsS "$base/stock/price/AAPL" >/dev/null
echo "stock price ok"

curl -fsS -X POST "$base/orders/stock/buy" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","quantity":1,"order_type":"buy","price":211.5}' >/dev/null
echo "stock buy ok"

curl -fsS "$base/orders" >/dev/null
echo "orders ok"
