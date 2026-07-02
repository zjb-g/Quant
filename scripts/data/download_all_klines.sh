#!/usr/bin/env bash
# 双轨 K 线下载编排：
#   主流币（Binance 有数据）→ scripts/download_binance_data.py
#   OKX 独有小币         → scripts/download_okx_data.py
#
# 用法：
#   bash scripts/download_all_klines.sh
#   START=2022-01-01 bash scripts/download_all_klines.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-.venv/bin/python}"
START="${START:-2020-01-01}"
END="${END:-$(date -u +%Y-%m-%d)}"
LOG_DIR="user_data/logs"
mkdir -p "$LOG_DIR" user_data/data/binance user_data/data/okx

LOG="$LOG_DIR/download_klines_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "=============================================="
echo " 双轨 K 线下载  $START ~ $END"
echo " 日志: $LOG"
echo "=============================================="

# ---- Tier 1：交易最多的主流币，全周期长历史 ----
TIER1_BINANCE="BTCUSDT ETHUSDT SUIUSDT ZECUSDT XRPUSDT DOGEUSDT SOLUSDT"
TIER1_INTERVALS="1m 5m 15m 1h 4h 12h 1d"

echo ""
echo ">>> [1/4] Binance Tier1 主流币 全周期 ($TIER1_BINANCE)"
for IV in $TIER1_INTERVALS; do
  echo "--- interval=$IV ---"
  $PYTHON scripts/data/download_binance_data.py \
    --symbols $TIER1_BINANCE \
    --interval "$IV" \
    --start "$START" \
    --end "$END" || echo "[warn] Binance $IV 部分失败，继续"
done

# ---- Tier 2：Binance 有、交易较少的币，中长周期 ----
TIER2_BINANCE="ORDIUSDT FLOWUSDT ZENUSDT WLDUSDT ONTUSDT MAGICUSDT FILUSDT BNBUSDT UNIUSDT TRXUSDT LPTUSDT"
TIER2_INTERVALS="15m 1h 4h 1d"
TIER2_START="${TIER2_START:-2022-01-01}"

echo ""
echo ">>> [2/4] Binance Tier2 次要币 中长周期 ($TIER2_BINANCE)"
for IV in $TIER2_INTERVALS; do
  echo "--- interval=$IV ---"
  $PYTHON scripts/data/download_binance_data.py \
    --symbols $TIER2_BINANCE \
    --interval "$IV" \
    --start "$TIER2_START" \
    --end "$END" || echo "[warn] Binance Tier2 $IV 部分失败，继续"
done

# ---- Tier 3：OKX 独有小币（Binance 无数据），API 拉取 ----
# 按历史持仓交易量排序，>=5 笔的币
OKX_ONLY_INSTS="LAB-USDT-SWAP IP-USDT-SWAP HYPE-USDT-SWAP BEAT-USDT-SWAP SPCX-USDT-SWAP NIGHT-USDT-SWAP MU-USDT-SWAP BONK-USDT-SWAP NC-USDT-SWAP SNDK-USDT-SWAP BSB-USDT-SWAP BABY-USDT-SWAP TRUMP-USDT-SWAP WDC-USDT-SWAP H-USDT-SWAP MMT-USDT-SWAP XAU-USDT-SWAP ALLO-USDT-SWAP"
OKX_INTERVALS="15m 1h 4h 1d"
OKX_START="${OKX_START:-2023-01-01}"

echo ""
echo ">>> [3/4] OKX 独有小币 ($OKX_ONLY_INSTS)"
$PYTHON scripts/data/download_okx_data.py \
  --insts $OKX_ONLY_INSTS \
  --intervals $OKX_INTERVALS \
  --start "$OKX_START" \
  --end "$END" || echo "[warn] OKX 部分失败，继续"

# ---- 汇总 ----
echo ""
echo ">>> [4/4] 下载汇总"
echo "Binance 数据:"
du -sh user_data/data/binance 2>/dev/null || echo "  (空)"
ls user_data/data/binance/*.feather 2>/dev/null | wc -l | xargs -I{} echo "  feather 文件: {} 个"
echo "OKX 数据:"
du -sh user_data/data/okx 2>/dev/null || echo "  (空)"
ls user_data/data/okx/*.feather 2>/dev/null | wc -l | xargs -I{} echo "  feather 文件: {} 个"
echo ""
echo "全部完成。日志: $LOG"
