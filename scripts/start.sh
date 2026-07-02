#!/usr/bin/env bash
# 一键启动 Web（API + 前端静态资源，单端口 8000）
#
# 用法:
#   bash scripts/start.sh              # 后台启动（推荐）
#   bash scripts/start.sh --foreground # 前台启动（调试用）
#   bash scripts/start.sh --build      # 强制重新构建前端
#   bash scripts/start.sh --build --foreground
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${WEB_PORT:-8000}"
PID_FILE="$ROOT/user_data/logs/web.pid"
LOG_FILE="$ROOT/user_data/logs/web.log"
FOREGROUND=0
FORCE_BUILD=0

for arg in "$@"; do
  case "$arg" in
    --foreground|-f) FOREGROUND=1 ;;
    --build|-b) FORCE_BUILD=1 ;;
    --help|-h)
      echo "用法: bash scripts/start.sh [--build] [--foreground]"
      echo "  --build       强制重新构建 frontend/dist"
      echo "  --foreground  前台运行（默认后台 + 写 PID）"
      exit 0
      ;;
    *) echo "未知参数: $arg"; exit 1 ;;
  esac
done

mkdir -p "$ROOT/user_data/logs"

if [ ! -x "$ROOT/.venv/bin/uvicorn" ]; then
  echo "[start] ❌ 未找到 .venv，请先执行:"
  echo "       python3 -m venv .venv && .venv/bin/pip install -e '.[dev,freqtrade]'"
  exit 1
fi

if [ ! -f "$ROOT/.env" ]; then
  echo "[start] ⚠️  未找到 .env，从模板复制..."
  cp "$ROOT/.env.example" "$ROOT/.env"
fi

stop_pid() {
  local pid="$1"
  if kill -0 "$pid" 2>/dev/null; then
    echo "[start] 停止旧进程 PID=$pid"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 15); do
      kill -0 "$pid" 2>/dev/null || return 0
      sleep 1
    done
    kill -9 "$pid" 2>/dev/null || true
  fi
}

echo "[start] 清理端口 ${PORT} 上的旧 Web 进程..."
if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$old_pid" ]; then
    stop_pid "$old_pid"
  fi
  rm -f "$PID_FILE"
fi

while read -r pid; do
  [ -n "$pid" ] && stop_pid "$pid"
done < <(pgrep -f "uvicorn quant_guard.api.app:app" 2>/dev/null || true)

if command -v ss >/dev/null 2>&1; then
  while read -r pid; do
    [ -n "$pid" ] && stop_pid "$pid"
  done < <(ss -tlnp 2>/dev/null | grep ":${PORT}" | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u || true)
fi

echo "[start] 检查前端构建..."
if [ "$FORCE_BUILD" = 1 ] || [ ! -f "$ROOT/frontend/dist/index.html" ]; then
  echo "[start] 构建前端（vite build）..."
  (cd "$ROOT/frontend" && PATH=/usr/bin:$PATH npx vite build)
else
  echo "[start] 使用已有 frontend/dist（加 --build 可强制重建）"
fi

UVICORN_CMD=(
  "$ROOT/.venv/bin/uvicorn" quant_guard.api.app:app
  --host 0.0.0.0
  --port "$PORT"
  --timeout-keep-alive 30
)

echo "[start] 启动 API + 前端 → http://0.0.0.0:${PORT}"

if [ "$FOREGROUND" = 1 ]; then
  echo "[start] 前台模式（Ctrl+C 停止）"
  exec "${UVICORN_CMD[@]}"
fi

nohup "${UVICORN_CMD[@]}" >>"$LOG_FILE" 2>&1 &
new_pid=$!
echo "$new_pid" >"$PID_FILE"

echo "[start] 等待服务就绪..."
ok=0
for _ in $(seq 1 30); do
  if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/api/auth/status" >/dev/null 2>&1; then
    ok=1
    break
  fi
  if ! kill -0 "$new_pid" 2>/dev/null; then
    echo "[start] ❌ 进程已退出，最近日志:"
    tail -20 "$LOG_FILE" 2>/dev/null || true
    rm -f "$PID_FILE"
    exit 1
  fi
  sleep 1
done

if [ "$ok" != 1 ]; then
  echo "[start] ❌ 启动超时，请查看日志: $LOG_FILE"
  exit 1
fi

ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "=========================================="
echo "  ✅ Web 已启动"
echo "  PID:     $new_pid"
echo "  日志:    $LOG_FILE"
echo "  本机:    http://127.0.0.1:${PORT}"
if [ -n "$ip" ]; then
  echo "  公网:    http://${ip}:${PORT}"
fi
echo "  停止:    bash scripts/stop.sh"
echo "  状态:    bash scripts/status.sh"
echo "=========================================="
echo ""
echo "说明: dry-run Bot 在 Web「控制台」页启动，不包含在此脚本内。"
