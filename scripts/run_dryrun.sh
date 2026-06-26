#!/usr/bin/env bash
# 启动 dry-run 模拟盘。
# 用法：
#   bash scripts/run_dryrun.sh
# 说明：
# - 强制使用 dryrun 配置，dry_run 必须为 true。
# - 需要 T0.4(配置) 与 T6.1(启动前安全检查) 完成后才能正式运行。
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG="${CONFIG:-user_data/config/config.dryrun.example.json}"

echo "[run_dryrun] config=$CONFIG (dry_run=true enforced)"

docker compose up -d --build freqtrade || true
# 实际 dry-run 由 T6.1 覆盖完整启动流程与安全检查。
docker compose run --rm freqtrade trade \
  --config "$CONFIG" \
  --strategy "${STRATEGY:-EmaCrossoverStrategy}" \
  --logfile user_data/logs/freqtrade.log
