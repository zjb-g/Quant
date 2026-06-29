#!/usr/bin/env bash
# 启动 dry-run 模拟盘（T6.1 完善）。
# 用法：
#   bash scripts/run_dryrun.sh
#   STRATEGY=FundingRateTrendStrategy bash scripts/run_dryrun.sh
# 说明：
# - 启动前自动执行安全检查（precheck_dryrun.py）
# - 强制 dry_run=true
# - 检查通过后才启动 Freqtrade
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG="${CONFIG:-user_data/config/config.dryrun.example.json}"
STRATEGY="${STRATEGY:-EmaCrossoverStrategy}"

echo "[run_dryrun] config=$CONFIG strategy=$STRATEGY"
echo "[run_dryrun] 执行启动前安全检查..."

# 安全检查
python scripts/precheck_dryrun.py --config "$CONFIG"
if [ $? -ne 0 ]; then
    echo "[run_dryrun] ❌ 安全检查未通过，拒绝启动"
    exit 1
fi

echo "[run_dryrun] ✅ 安全检查通过，启动 dry-run..."

# 优先用本地 Freqtrade，其次 Docker
if command -v freqtrade &> /dev/null; then
    freqtrade trade \
        --config "$CONFIG" \
        --strategy "$STRATEGY" \
        --userdir user_data \
        --logfile user_data/logs/freqtrade.log
else
    docker compose run --rm freqtrade trade \
        --config "$CONFIG" \
        --strategy "$STRATEGY" \
        --logfile user_data/logs/freqtrade.log
fi
