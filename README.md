# Crypto Quant System

个人加密永续合约量化交易系统 —— 基于 Freqtrade + OKX USDT 永续合约 + 风控护栏 + Telegram 监控。

> 本仓库由 `CURSOR_AI_DEVELOPMENT_COMMANDER.md` 指挥开发，严格分阶段、逐任务推进。
> 未经 `docs/LIVE_SAFETY_CHECKLIST.md` 全部通过，禁止进入实盘。

## 目标

```
策略研究 → 可信回测(含资金费/手续费/强平) → dry-run → 小资金实盘 → 风控闭环 + Telegram 监控
```

核心原则：不自研造轮子，复用 Freqtrade / CCXT；研究、回测、模拟盘、实盘同一份策略代码；安全优先于收益；风控模块是下单前强制关卡。

## 技术栈

| 层级 | 技术 |
|---|---|
| 主框架 | Freqtrade |
| 交易所接口 | CCXT / Freqtrade 内置 exchange 层 |
| 主交易所 | OKX |
| 交易品种 | USDT 本位永续合约 |
| 语言 | Python 3.11+ |
| 配置 | JSON / YAML / `.env` |
| 部署 | Docker Compose |
| 告警控制 | Telegram Bot |
| 测试 | pytest |

## 项目关键参数（决策记录）

详见 `docs/DECISIONS.md`。摘要：

- 交易品种：BTC / ETH / SOL / BNB / XRP（5 币 USDT 永续）
- 策略主时间框架：15m
- 持仓模式：双向持仓（支持对冲），最高杠杆 5x
- 小资金实盘规模：≤ 1000 USDT
- OKX 账户模式：统一账户（Unified）
- 资金费结算频率：每 8h（00/08/16 UTC）

## 目录结构

```
crypto-quant-system/
├── user_data/          # Freqtrade 习惯目录（策略/配置/数据/日志/回测结果）
├── quant_guard/        # 自研风控/执行增强/监控/回测校验层
├── scripts/            # 运维脚本
├── tests/              # 测试
└── docs/               # 文档与阶段门禁记录
```

## 快速开始（待 T0.2 完成后可用）

```bash
cp .env.example .env            # 填入占位（dry-run 阶段可为空）
docker compose config           # 校验 compose
bash scripts/download_data.sh   # 下载历史数据
bash scripts/run_backtest.sh    # 运行回测
```

## 安全声明

- 默认只允许 backtest / dry-run，禁止 live trading。
- 所有下单路径必须经过 `quant_guard.risk.RiskManager`。
- API Key、Secret、Passphrase 不得写入代码库，统一从 `.env` 读取。
- 系统不包含任何提币 / 资金划转逻辑。
- 实盘前必须完成 `docs/LIVE_SAFETY_CHECKLIST.md` 全部检查项。

## 开发指挥

开发顺序与任务编号见 `CURSOR_AI_DEVELOPMENT_COMMANDER.md`，当前进度见 `docs/PROJECT_STATE.md`。
