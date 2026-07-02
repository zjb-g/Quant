#!/usr/bin/env bash
# 统一 K 线下载入口
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
CMD="${1:-all}"

case "$CMD" in
  all)
    exec bash scripts/data/download_all_klines.sh
    ;;
  binance)
    PYTHON="${PYTHON:-.venv/bin/python}"
    START="${START:-2020-01-01}"
    END="${END:-$(date -u +%Y-%m-%d)}"
    SYMBOLS="${SYMBOLS:-BTCUSDT ETHUSDT SOLUSDT BNBUSDT XRPUSDT}"
    INTERVAL="${INTERVAL:-15m}"
    exec "$PYTHON" scripts/data/download_binance_data.py \
      --symbols $SYMBOLS --interval "$INTERVAL" --start "$START" --end "$END"
    ;;
  okx)
    PYTHON="${PYTHON:-.venv/bin/python}"
    exec "$PYTHON" scripts/data/download_okx_data.py "${@:2}"
    ;;
  freqtrade|docker)
    exec bash scripts/data/download_data.sh
    ;;
  -h|--help|help)
    sed -n '2,8p' "$0"
    ;;
  *)
    echo "未知子命令: $CMD（可用: all | binance | okx | freqtrade）" >&2
    exit 1
    ;;
esac
