# Crypto Quant System

个人加密永续合约量化交易系统 —— 基于 Freqtrade + OKX USDT 永续合约 + 风控护栏 + Web 控制台。

> 未经 `docs/LIVE_SAFETY_CHECKLIST.md` 全部通过，禁止进入实盘。

## 目标

```
策略研究 → 可信回测 → Web 复盘/分析 → dry-run → 小资金实盘 → 风控闭环
```

## 技术栈

| 层级 | 技术 |
|---|---|
| 主框架 | Freqtrade |
| 交易所 | OKX（CCXT） |
| 自研层 | quant_guard（风控 / 执行 / K 线 / 分析） |
| 前端 | React + Vite + Ant Design |
| 后端 API | FastAPI（单端口 8000 托管前端） |
| 测试 | pytest |

## 快速开始

```bash
cp .env.example .env          # 填入 OKX / DeepSeek 等密钥
python -m venv .venv && .venv/bin/pip install -e ".[dev,freqtrade]"

# 一键启动 Web（API + 前端，后台运行）
bash start.sh
# 或: bash scripts/start.sh
# 停止: bash scripts/stop.sh
# 状态: bash scripts/status.sh
# 强制重建前端: bash start.sh --build
# 浏览器打开 http://localhost:8000
```

### 下载 K 线

```bash
bash scripts/download_klines.sh all        # 推荐：Binance + OKX 双轨
bash scripts/download_klines.sh binance    # 仅 Binance
bash scripts/download_klines.sh okx        # 仅 OKX 小币
```

### 回测与 dry-run

```bash
bash scripts/run_backtest.sh               # CLI 回测
# 或在 Web「回测分析」页运行

bash scripts/precheck_dryrun.py            # dry-run 启动前检查
# 或在 Web「控制台」启动 Freqtrade dry-run
```

## Web 功能

| 页面 | 功能 |
|---|---|
| 仪表盘 | Bot 状态、持仓、权益曲线、风控 |
| 回测分析 | Web 触发 Freqtrade 回测 |
| 策略管理 | 策略 CRUD + AI 生成 |
| 交易所 | OKX 连接、余额、持仓 |
| 持仓复盘 | K 线 + 进出场标注 |
| 持仓分析 | 胜率/杠杆分组 + AI 分析 |
| 控制台 | Bot 启停、Kill Switch、紧急全平 |
| 告警 | 系统事件 |

## 安全声明

- 默认只允许 backtest / dry-run。
- Kill Switch 会**停止 Bot** 并阻断新开仓；紧急全平经 `ExecutionEngine` + `RiskManager`。
- 真实平仓需 `LIVE_TRADING_CONFIRMED=true`。
- API Key 不得入库，统一从 `.env` 读取。
- **公网暴露**前必须启用 JWT 登录，见 [docs/PUBLIC_ACCESS.md](docs/PUBLIC_ACCESS.md)。

## 目录结构

```
crypto-quant-system/
├── quant_guard/        # 风控 / 执行 / API / 服务层
├── user_data/          # Freqtrade 策略 / 配置 / 数据
├── frontend/           # React 前端
├── scripts/            # 运维脚本
├── tests/              # pytest
└── docs/               # 阶段门禁与决策记录
```

开发进度见 `docs/PROJECT_STATE.md`。
