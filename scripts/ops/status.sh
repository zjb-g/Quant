#!/usr/bin/env bash
# 查看 Web 服务状态
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PID_FILE="$ROOT/user_data/logs/web.pid"
LOG_FILE="$ROOT/user_data/logs/web.log"
PORT="${WEB_PORT:-8000}"

echo "=== Web 服务 ==="
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "状态: 运行中 (PID=$(cat "$PID_FILE"))"
else
  running="$(pgrep -af 'uvicorn quant_guard.api.app' 2>/dev/null | head -1 || true)"
  if [ -n "$running" ]; then
    echo "状态: 运行中（无 PID 文件）"
    echo "$running"
  else
    echo "状态: 已停止"
  fi
fi

if curl -sf --max-time 3 "http://127.0.0.1:${PORT}/api/auth/status" >/dev/null 2>&1; then
  echo "健康: ✅ http://127.0.0.1:${PORT}/api/auth/status"
else
  echo "健康: ❌ 无响应"
fi

ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "$ip" ] && echo "访问: http://${ip}:${PORT}"

echo ""
echo "=== Freqtrade dry-run ==="
ft_pid="$(cat "$ROOT/user_data/logs/freqtrade.pid" 2>/dev/null || true)"
if [ -n "$ft_pid" ] && kill -0 "$ft_pid" 2>/dev/null; then
  echo "状态: 运行中 (PID=$ft_pid)"
else
  ft="$(pgrep -af 'freqtrade trade' 2>/dev/null | head -1 || true)"
  if [ -n "$ft" ]; then
    echo "状态: 运行中"
    echo "$ft"
  else
    echo "状态: 已停止（在 Web 控制台启动）"
  fi
fi

[ -f "$LOG_FILE" ] && echo "" && echo "最近 Web 日志:" && tail -5 "$LOG_FILE"
