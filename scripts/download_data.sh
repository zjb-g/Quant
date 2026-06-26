#!/usr/bin/env bash
# 下载 OKX USDT 永续合约历史数据。
# 默认下载 BTC/ETH/SOL/BNB/XRP 的 15m + 1h K线，最近 365 天。
# 用法：
#   bash scripts/download_data.sh
#   DAYS=730 bash scripts/download_data.sh
#   PAIRS="BTC/USDT:USDT ETH/USDT:USDT" bash scripts/download_data.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PAIRS="${PAIRS:-BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT BNB/USDT:USDT XRP/USDT:USDT}"
TIMEFRAMES="${TIMEFRAMES:-15m 1h}"
DAYS="${DAYS:-365}"

echo "[download_data] exchange=okx trading_mode=futures"
echo "[download_data] pairs=$PAIRS"
echo "[download_data] timeframes=$TIMEFRAMES"
echo "[download_data] days=$DAYS"

docker compose run --rm freqtrade download-data \
  --exchange okx \
  --trading-mode futures \
  --pairs $PAIRS \
  --timeframes $TIMEFRAMES \
  --days "$DAYS"
