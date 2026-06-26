#!/usr/bin/env bash
# 运行 quant_guard 全部测试。
# 优先使用本地 Python 环境；若失败可改用容器。
# 用法：
#   bash scripts/run_tests.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[run_tests] running pytest on tests/"
python -m pytest tests/ -v
