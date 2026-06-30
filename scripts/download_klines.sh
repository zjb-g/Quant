#!/usr/bin/env bash
# 统一 K 线下载入口
#
# 用法：
#   bash scripts/download_klines.sh all          # 双轨全量（Binance + OKX 小币）默认
#   bash scripts/download_klines.sh binance      # 仅 Binance feather
#   bash scripts/download_klines.sh okx          # 仅 OKX 小币
#   bash scripts/download_klines.sh freqtrade      # Docker Freqtrade 下载（需 docker compose）
set -euo pipefail

cd "$(dirname "$0")/.."
CMD="${1:-all}"

case "$CMD" in
  all)
    exec bash scripts/download_all_klines.sh
    ;;
  binance)
    PYTHON="${PYTHON:-.venv/bin/python}"
    START="${START:-2020-01-01}"
    END="${END:-$(date -u +%Y-%m-%d)}"
    SYMBOLS="${SYMBOLS:-BTCUSDT ETHUSDT SOLUSDT BNBUSDT XRPUSDT}"
    INTERVAL="${INTERVAL:-15m}"
    exec "$PYTHON" scripts/download_binance_data.py \
      --symbols $SYMBOLS --interval "$INTERVAL" --start "$START" --end "$END"
    ;;
  okx)
    PYTHON="${PYTHON:-.venv/bin/python}"
    exec "$PYTHON" scripts/download_okx_data.py "${@:2}"
    ;;
  freqtrade|docker)
    exec bash scripts/download_data.sh
    ;;
  -h|--help|help)
    sed -n '2,9p' "$0"
    ;;
  *)
    echo "未知子命令: $CMD（可用: all | binance | okx | freqtrade）" >&2
    exit 1
    ;;
esac
