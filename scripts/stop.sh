#!/usr/bin/env bash
# 停止 Web 服务（API + 前端）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT/user_data/logs/web.pid"
PORT="${WEB_PORT:-8000}"

stop_pid() {
  local pid="$1"
  if kill -0 "$pid" 2>/dev/null; then
    echo "[stop] 停止 PID=$pid"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "$pid" 2>/dev/null || return 0
      sleep 1
    done
    kill -9 "$pid" 2>/dev/null || true
  fi
}

if [ -f "$PID_FILE" ]; then
  stop_pid "$(cat "$PID_FILE")"
  rm -f "$PID_FILE"
fi

while read -r pid; do
  [ -n "$pid" ] && stop_pid "$pid"
done < <(pgrep -f "uvicorn quant_guard.api.app:app" 2>/dev/null || true)

if curl -sf --max-time 1 "http://127.0.0.1:${PORT}/api/auth/status" >/dev/null 2>&1; then
  echo "[stop] ⚠️  端口 ${PORT} 仍有响应，请手动检查"
else
  echo "[stop] ✅ Web 已停止"
fi
