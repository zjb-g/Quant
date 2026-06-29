# VPS 部署说明

> 本文档指导如何在 VPS 上部署 Crypto Quant System。
> **警告**：进入 live 前必须完成 `docs/LIVE_SAFETY_CHECKLIST.md` 全部检查项。

## 1. 环境准备

### 1.1 VPS 要求

- OS: Ubuntu 22.04+ / Debian 12+
- CPU: 2 核+
- 内存: 4GB+
- 磁盘: 20GB+
- 网络: 可访问 OKX API（需配置代理或选择海外 VPS）

### 1.2 安装 Docker

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sudo sh

# 将当前用户加入 docker 组
sudo usermod -aG docker $USER

# 重新登录使组生效
exit
# 重新 SSH 登录

# 验证
docker --version
docker compose version
```

### 1.3 安装 Git

```bash
sudo apt install -y git
```

## 2. 项目部署

### 2.1 克隆仓库

```bash
cd ~
git clone https://github.com/zjb-g/Quant.git crypto-quant-system
cd crypto-quant-system
```

### 2.2 配置环境变量

```bash
cp .env.example .env
nano .env
```

编辑 `.env`：

```bash
# ---- OKX 交易所（dry-run 阶段可留空）----
OKX_API_KEY=
OKX_API_SECRET=
OKX_API_PASSPHRASE=
OKX_ACCOUNT_MODE=unified
OKX_POS_MODE=long_short

# ---- Telegram 监控 ----
TELEGRAM_BOT_TOKEN=你的Bot Token
TELEGRAM_CHAT_ID=你的Chat ID
TELEGRAM_ENABLED=true

# ---- 实盘安全开关（dry-run 阶段全 false）----
LIVE_TRADING_CONFIRMED=false
RISK_CONFIG_LOADED=false
KILL_SWITCH_TESTED=false

# ---- 风控参数 ----
RISK_MAX_LEVERAGE=5
RISK_MAX_SINGLE_ORDER_NOTIONAL=200
RISK_MAX_TOTAL_NOTIONAL=1000
```

### 2.3 下载历史数据

```bash
# 方式 1：用 Binance 公开数据（免费，无需 API Key）
python scripts/download_binance_data.py --start 2025-06-26 --end 2026-06-26

# 方式 2：用 Freqtrade 下载 OKX 数据（需 OKX API 可达）
bash scripts/download_data.sh
```

### 2.4 校验 Docker Compose

```bash
docker compose config
```

## 3. 启动 Dry-run

### 3.1 安全检查

```bash
python scripts/precheck_dryrun.py
```

### 3.2 启动

```bash
# 方式 1：本地 Freqtrade（推荐，便于调试）
pip install freqtrade
bash scripts/run_dryrun.sh

# 方式 2：Docker
docker compose up -d freqtrade
```

### 3.3 查看日志

```bash
# 本地
tail -f user_data/logs/freqtrade.log

# Docker
docker compose logs -f freqtrade
```

### 3.4 停止

```bash
# 本地：Ctrl+C

# Docker
docker compose stop freqtrade
```

## 4. 启动 Web UI（可选）

### 4.1 启动后端 API

```bash
# 本地
pip install fastapi uvicorn
python -m uvicorn quant_guard.api.app:app --port 8000

# Docker
docker compose up -d api
```

### 4.2 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://VPS_IP:5173 查看 Web UI。

## 5. 进入 Live（⚠️ 高风险）

### 5.1 前置条件

**必须完成 `docs/LIVE_SAFETY_CHECKLIST.md` 全部检查项后才能继续！**

### 5.2 配置 OKX API Key

1. 登录 OKX → API 管理 → 创建 API Key
2. **权限设置**：只勾选"读取"和"交易"，**禁用"提币"**
3. 将 Key/Secret/Passphrase 填入 `.env`

### 5.3 启用 live 开关

编辑 `.env`：

```bash
LIVE_TRADING_CONFIRMED=true
RISK_CONFIG_LOADED=true
KILL_SWITCH_TESTED=true
TELEGRAM_ENABLED=true
```

### 5.4 启动 live

```bash
# 复制 live 配置模板
cp user_data/config/config.live.example.json user_data/config/config.live.json

# 替换占位符（或手动编辑）
# 设置 OKX_API_KEY 等环境变量后

# 启动
freqtrade trade --config user_data/config/config.live.json --strategy EmaCrossoverStrategy --userdir user_data
```

## 6. 运维

### 6.1 备份

```bash
# 备份 user_data（策略/配置/数据/日志/回测结果）
tar -czf backup_$(date +%Y%m%d).tar.gz user_data/

# 备份到远程（可选）
scp backup_*.tar.gz user@remote:/backup/
```

### 6.2 恢复

```bash
# 停止服务
docker compose stop

# 恢复备份
tar -xzf backup_YYYYMMDD.tar.gz

# 重新启动
docker compose up -d
```

### 6.3 更新代码

```bash
git pull origin main
docker compose up -d --build
```

### 6.4 紧急操作

```bash
# 紧急全平（默认安全，仅打印计划）
python scripts/emergency_close_all.py

# 真实执行紧急全平（需二次确认）
python scripts/emergency_close_all.py --confirm-live

# 或通过 Telegram
# 发送 /emergency_close_all，然后 60 秒内再次发送确认
```

## 7. 监控

### 7.1 Docker 状态

```bash
docker compose ps
docker compose stats
```

### 7.2 心跳检查

```bash
# 手动检查
python -c "from quant_guard.monitoring.heartbeat import check_health; print('healthy' if check_health() else 'unhealthy')"
```

### 7.3 日志轮转

Docker 已配置日志限制（50m × 3 文件）。本地日志在 `user_data/logs/`。

## 8. 常见问题

### Q: OKX API 不可达？
A: 国内 VPS 需配置代理，或使用海外 VPS（新加坡/日本/美国）。

### Q: 回测报错 "ExchangeNotAvailable"？
A: Freqtrade 回测时需连交易所加载 markets。本机不可达时，用 gate.io 配置或下载数据后离线回测。

### Q: Docker healthcheck 失败？
A: 检查 `user_data/logs/heartbeat.json` 是否存在且未超时。首次启动需 60 秒（start_period）。

### Q: live_guard 拒绝启动？
A: 检查 `.env` 中 4 个 LIVE_* 变量是否全为 true，且 OKX 密钥已填入。

---

**⚠️ 最终提醒**：live trading 有风险，可能损失全部本金。请确保：
1. 已完成 LIVE_SAFETY_CHECKLIST 全部检查
2. 实盘规模 ≤ 1000 USDT（可承受全部亏损）
3. Telegram 告警已测试可用
4. 紧急全平流程已演练
