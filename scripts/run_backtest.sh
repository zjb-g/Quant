#!/usr/bin/env bash
# 运行 Freqtrade 回测。
# 用法：
#   bash scripts/run_backtest.sh                      # 默认策略
#   STRATEGY=FundingRateTrendStrategy bash scripts/run_backtest.sh
#   TIMERANGE=20250101-20260101 bash scripts/run_backtest.sh
# 说明：需要 T0.3(策略) 与 T0.4(配置) 完成后才能真正跑通回测。
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG="${CONFIG:-user_data/config/config.dryrun.example.json}"
STRATEGY="${STRATEGY:-EmaCrossoverStrategy}"
TIMERANGE="${TIMERANGE:-}"

ARGS=(backtest --config "$CONFIG" --strategy "$STRATEGY")
if [ -n "$TIMERANGE" ]; then
  ARGS+=(--timerange "$TIMERANGE")
fi

echo "[run_backtest] config=$CONFIG strategy=$STRATEGY timerange=${TIMERANGE:-none}"

docker compose run --rm freqtrade "${ARGS[@]}"
