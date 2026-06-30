#!/usr/bin/env bash
# 一键启动 Web 服务（API + 前端，单端口 8000）
# 用法：bash scripts/start_web.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[start_web] 检查前端构建..."
if [ ! -f frontend/dist/index.html ]; then
  echo "[start_web] 构建前端（首次约 10 秒）..."
  cd frontend
  PATH=/usr/bin:$PATH npx vite build
  cd ..
fi

echo "[start_web] 启动 API + 前端 → http://0.0.0.0:8000"
echo "[start_web] Cursor 远程请转发端口 8000，浏览器打开 http://localhost:8000"
exec .venv/bin/uvicorn quant_guard.api.app:app --host 0.0.0.0 --port 8000
