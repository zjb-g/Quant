# Cursor AI 主导开发总指挥文档

## 项目：个人加密永续合约量化交易系统

> 本文档用于放入项目根目录，作为 Cursor / AI Agent 的长期开发指挥文件。  
> Cursor 必须以本文档为最高开发依据，逐阶段、逐任务完成开发，不允许一次性生成全项目代码。

---

## 0. 给 Cursor 的最高指令

你是本项目的 AI 软件工程师。你的职责不是自由发挥，而是严格按照本文档完成一个基于 **Freqtrade + OKX 永续合约 + 风控护栏 + Telegram 监控** 的个人量化交易系统。

你必须遵守：

1. **一次只执行一个任务编号**，例如 `T0.1`、`T1.2`、`T3.4`。
2. **没有用户明确要求，不得跳阶段**。
3. **不得一次性重写整个项目**。
4. **不得擅自删除已有文件**，除非用户明确要求。
5. **不得把 API Key、Secret、Passphrase 写入代码库**。
6. **默认只允许 backtest / dry-run，不允许 live trading**。
7. **任何实盘相关代码必须带安全开关**。
8. **所有下单路径必须经过风控模块，不允许策略直接绕过风控下单**。
9. **每次修改后必须说明：改了哪些文件、为什么改、如何运行验证**。
10. **每个任务完成后必须更新 `docs/TASK_LOG.md` 和 `docs/PROJECT_STATE.md`。**

---

## 1. 项目目标

本项目目标是构建一个个人加密永续合约量化交易系统，实现：

```text
策略研究 → 回测 → 模拟盘 dry-run → 小资金实盘 → 监控告警 → 风控闭环
```

核心原则：

- 不自研造轮子，优先复用 Freqtrade / CCXT。
- 研究、回测、模拟盘、实盘尽量使用同一份策略代码。
- 安全优先于收益。
- 风控模块是下单前的强制关卡。
- 初期不做 Web 前端、不做 Kubernetes、不做微服务、不做高频做市。

---

## 2. 技术栈锁定

Cursor 不得擅自更换技术栈。

| 层级 | 技术 |
|---|---|
| 主框架 | Freqtrade |
| 交易所接口 | CCXT / Freqtrade 内置 exchange 层 |
| 主交易所 | OKX |
| 交易品种 | USDT 本位永续合约 |
| 语言 | Python 3.11+ |
| 策略 | Freqtrade Strategy 类 |
| 初期数据库 | SQLite / Freqtrade 默认存储 |
| 配置 | JSON / YAML / `.env` |
| 部署 | Docker Compose |
| 告警控制 | Telegram Bot |
| 测试 | pytest |
| 代码质量 | ruff / mypy 可选 |

---

## 2.5 项目关键参数决策（用户已确认锁定，2026-06-26）

以下参数由用户确认，Cursor 不得擅自更改。详细 ADR 见 `docs/DECISIONS.md`。

| 参数 | 决策值 | 影响任务 |
|---|---|---|
| 交易所 | OKX | T1.1 / T0.4 |
| 账户模式 | 统一账户（Unified） | T1.1 / T2.2 |
| 持仓模式 | 双向持仓（long_short，支持对冲） | T0.4 / T2.2 / T4.x |
| 最高杠杆 | 5x | T3.2（RISK-03） |
| 交易品种 | BTC/ETH/SOL/BNB/XRP（5 币 USDT 永续） | T0.4 / T1.x |
| 策略主时间框架 | 15m | T0.3 / T1.3 |
| 小资金实盘规模 | ≤ 1000 USDT | T3.2（RISK-01/02/03 默认值） |
| 资金费结算频率 | 每 8h（00/08/16 UTC） | T2.1 |
| 历史数据范围 | 至少 1 年（建议 2 年） | T0.2 / T1.x |

基于 ≤1000 USDT 实盘规模，风控默认参数（可在 `risk_config.yaml` 覆盖）：

```text
max_single_order_notional = 200   # 单笔下单名义价值上限
max_symbol_notional       = 300   # 单币敞口上限
max_total_notional        = 1000  # 总敞口上限
max_leverage              = 5
max_drawdown_stop_pct     = 15    # 最大回撤熔断
daily_loss_stop_pct       = 5     # 每日亏损限额
liquidation_distance_pct  = 10    # 强平距离阈值
```

---

## 3. 项目目录结构

Cursor 应优先建立并维护如下结构。

```text
crypto-quant-system/
│
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── pyproject.toml
│
├── user_data/
│   ├── strategies/
│   │   ├── EmaCrossoverStrategy.py
│   │   └── FundingRateTrendStrategy.py
│   ├── config/
│   │   ├── config.example.json
│   │   ├── config.dryrun.example.json
│   │   └── config.live.example.json
│   ├── data/
│   ├── logs/
│   └── backtest_results/
│
├── quant_guard/
│   ├── __init__.py
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   ├── rules.py
│   │   └── state.py
│   ├── exchange/
│   │   ├── __init__.py
│   │   ├── okx_client.py
│   │   └── models.py
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── order_manager.py
│   │   └── idempotency.py
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── telegram_bot.py
│   │   ├── alerts.py
│   │   └── heartbeat.py
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── funding_fee.py
│   │   ├── liquidation.py
│   │   └── report.py
│   └── utils/
│       ├── __init__.py
│       ├── config_loader.py
│       ├── logging.py
│       └── time_sync.py
│
├── scripts/
│   ├── download_data.sh
│   ├── run_backtest.sh
│   ├── run_dryrun.sh
│   ├── run_tests.sh
│   └── emergency_close_all.py
│
├── tests/
│   ├── test_risk_manager.py
│   ├── test_okx_client.py
│   ├── test_execution_engine.py
│   ├── test_funding_fee.py
│   └── test_liquidation.py
│
└── docs/
    ├── PROJECT_STATE.md
    ├── TASK_LOG.md
    ├── PHASE_GATE_CHECKLIST.md
    ├── BACKTEST_VALIDATION.md
    ├── DRYRUN_VALIDATION.md
    └── LIVE_SAFETY_CHECKLIST.md
```

说明：

- `user_data/` 遵循 Freqtrade 项目习惯。
- `quant_guard/` 是本项目自己补齐的风控、执行增强、监控、回测校验层。
- 策略文件必须放在 `user_data/strategies/`。
- 配置模板必须放在 `user_data/config/`。
- 不允许把真实密钥写入配置模板。

---

## 4. Cursor 工作协议

每次用户让你执行某个任务时，你必须按以下顺序工作：

```text
1. 读取本文档
2. 读取 docs/PROJECT_STATE.md
3. 读取 docs/TASK_LOG.md
4. 确认当前任务编号
5. 只修改该任务允许修改的文件
6. 写代码
7. 写测试或补测试
8. 给出运行命令
9. 说明验收结果
10. 更新 PROJECT_STATE 和 TASK_LOG
```

每次输出必须包含：

```text
本次任务：Tx.x
修改文件：...
新增文件：...
运行命令：...
验收结果：通过 / 未通过
下一步建议：...
```

---

## 5. 禁止事项

Cursor 严禁做以下事情：

```text
- 禁止直接生成 live trading 配置并默认启用。
- 禁止把 dry_run 设置为 false，除非用户明确要求进入实盘阶段。
- 禁止策略直接调用交易所下单接口。
- 禁止绕过 RiskManager。
- 禁止删除测试。
- 禁止在代码里硬编码 API Key。
- 禁止把提币权限、资金划转权限相关逻辑写进系统。
- 禁止加入高频交易、做市、订单簿撮合等初期非目标功能。
- 禁止引入 Kubernetes、消息队列、复杂微服务架构。
```

---

# 6. 开发阶段总览

| 阶段 | 目标 | 是否可进入下一阶段 |
|---|---|---|
| Ph0 | 环境跑通、项目骨架可运行 | 回测能跑通 |
| Ph1 | 策略与可信回测 | 样本外 / walk-forward 通过 |
| Ph2 | dry-run 模拟盘 | 连续运行 1–2 周且无重大偏离 |
| Ph3 | 小资金实盘护栏 | P0 风控、执行、监控、运维全部验证 |
| Ph4 | 增强迭代 | 不影响已有稳定实盘 |

---

# PHASE 0：项目初始化与最小可运行系统

## 阶段目标

让项目可以被 Docker 启动，可以下载历史数据，可以运行一个最小 Freqtrade 回测。

---

## T0.1 初始化仓库结构

### 任务目标

创建项目基础目录、配置文件、文档文件、脚本文件。

### Cursor 执行指令

```text
执行 T0.1：初始化项目仓库结构。

要求：
1. 按本文档第 3 节创建目录结构。
2. 创建空的 Python package 文件。
3. 创建 README.md、.gitignore、.env.example、pyproject.toml。
4. 创建 docs/PROJECT_STATE.md 和 docs/TASK_LOG.md。
5. 不写交易逻辑，只搭建骨架。
6. 完成后列出所有新增文件。
```

### 允许修改文件

```text
全新项目下允许创建所有基础文件。
```

### 验收标准

```text
- 目录结构存在。
- Python package 可被 import。
- docs/PROJECT_STATE.md 存在。
- docs/TASK_LOG.md 存在。
```

---

## T0.2 配置 Docker Compose 与 Freqtrade 基础环境

### 任务目标

让项目可以通过 Docker Compose 运行 Freqtrade。

### Cursor 执行指令

```text
执行 T0.2：配置 Docker Compose 与 Freqtrade 基础环境。

要求：
1. 编写 docker-compose.yml。
2. 使用官方 Freqtrade 镜像或合理的 Python/Freqtrade 环境。
3. 映射 user_data 目录。
4. 创建 scripts/run_backtest.sh。
5. 创建 scripts/download_data.sh。
6. 所有命令默认使用 dry-run/backtest，不允许实盘。
7. 不引入数据库服务、Redis、消息队列。
```

### 验收命令

```bash
docker compose config
bash scripts/run_backtest.sh
```

### 验收标准

```text
- docker compose config 成功。
- Freqtrade 命令可执行。
- 不需要真实 API Key 即可运行基础命令。
```

---

## T0.3 创建 Freqtrade 示例策略

### 任务目标

创建最小 EMA 交叉策略，证明回测链路可运行。

### Cursor 执行指令

```text
执行 T0.3：创建最小 Freqtrade EMA 交叉策略。

要求：
1. 在 user_data/strategies/EmaCrossoverStrategy.py 中实现策略。
2. 使用 EMA20 / EMA50。
3. 支持 long 和 short，但默认可先只开 long。
4. 不引入复杂风控。
5. 保持 Freqtrade Strategy 标准写法。
```

### 验收命令

```bash
bash scripts/download_data.sh
bash scripts/run_backtest.sh
```

### 验收标准

```text
- 回测能正常启动。
- 策略文件可被 Freqtrade 识别。
- 回测结果可输出。
```

---

## T0.4 创建配置模板

### 任务目标

创建 OKX 永续合约配置模板，但不包含真实密钥。

### Cursor 执行指令

```text
执行 T0.4：创建 Freqtrade 配置模板。

要求：
1. 创建 user_data/config/config.example.json。
2. 创建 user_data/config/config.dryrun.example.json。
3. 创建 user_data/config/config.live.example.json。
4. 默认 dry_run 必须为 true。
5. live 配置中也不得包含真实密钥，只使用环境变量占位。
6. 必须包含 OKX、USDT 永续、stake_currency、max_open_trades 等基础字段。
7. 必须写清楚 live 配置不可直接使用，需完成 PHASE 3 检查后才可启用。
```

### 验收标准

```text
- 配置 JSON 格式有效。
- dry_run 默认为 true。
- 无任何真实密钥。
```

---

# PHASE 1：数据层与策略研究

## 阶段目标

实现行情、资金费率、标记价格获取；实现一个可研究的中低频策略；建立样本外验证流程。

---

## T1.1 实现 OKX 数据客户端

### 任务目标

通过 CCXT 或 Freqtrade exchange 能力封装 OKX 数据读取。

### Cursor 执行指令

```text
执行 T1.1：实现 OKX 数据客户端。

要求：
1. 创建 quant_guard/exchange/okx_client.py。
2. 实现 OKXClient 类。
3. 支持获取：
   - latest price
   - OHLCV K线
   - funding rate
   - mark price
   - account positions（仅接口定义，默认不请求真实账户）
4. 所有私有接口必须从环境变量读取密钥。
5. 默认 public-only 模式。
6. 加入基础重试、超时、异常封装。
7. 创建 tests/test_okx_client.py，使用 mock，不访问真实交易所。
```

### 允许修改文件

```text
quant_guard/exchange/okx_client.py
tests/test_okx_client.py
quant_guard/exchange/models.py
```

### 验收命令

```bash
pytest tests/test_okx_client.py
```

### 验收标准

```text
- mock 测试通过。
- 没有硬编码 API Key。
- public-only 模式可实例化。
```

---

## T1.2 实现数据完整性校验

### 任务目标

对历史 K 线进行缺失、重复、异常值检查。

### Cursor 执行指令

```text
执行 T1.2：实现数据完整性校验模块。

要求：
1. 创建 quant_guard/backtest/data_quality.py。
2. 实现检查：
   - 缺失时间戳
   - 重复时间戳
   - OHLC 逻辑异常
   - volume 异常
3. 输出 DataQualityReport 数据结构。
4. 创建 tests/test_data_quality.py。
```

### 验收命令

```bash
pytest tests/test_data_quality.py
```

---

## T1.3 实现 FundingRateTrendStrategy

### 任务目标

实现第一版正式策略。

### Cursor 执行指令

```text
执行 T1.3：实现 FundingRateTrendStrategy。

要求：
1. 文件：user_data/strategies/FundingRateTrendStrategy.py。
2. 策略逻辑：
   - EMA20 / EMA50 判断趋势
   - ATR 过滤极端波动
   - funding rate 过滤过高持仓成本
   - 支持 long/short
3. 参数必须可配置。
4. 使用 Freqtrade Strategy 标准接口。
5. 不允许策略直接调用交易所下单。
6. 加入注释说明每个信号含义。
```

### 验收命令

```bash
bash scripts/run_backtest.sh FundingRateTrendStrategy
```

### 验收标准

```text
- 策略可被 Freqtrade 识别。
- 回测能运行。
- 有交易信号。
- 无前视数据使用。
```

---

## T1.4 建立样本外与 walk-forward 验证脚本

### 任务目标

建立防过拟合验证流程。

### Cursor 执行指令

```text
执行 T1.4：建立样本外与 walk-forward 验证脚本。

要求：
1. 创建 scripts/walk_forward_backtest.py。
2. 支持传入：
   - strategy
   - timerange
   - train window
   - test window
3. 输出 docs/BACKTEST_VALIDATION.md。
4. 不需要自动调参，先做窗口切分和结果汇总。
```

### 验收标准

```text
- 能按多个时间窗口运行回测。
- 输出每个窗口的收益、最大回撤、交易次数。
```

---

# PHASE 2：可信回测增强

## 阶段目标

确认手续费、资金费、强平风险在回测中被显式考虑，避免虚假收益。

---

## T2.1 实现资金费计算模块

### 任务目标

建立资金费成本计算逻辑，用于回测报告与实盘 PnL 统计。

### Cursor 执行指令

```text
执行 T2.1：实现资金费计算模块。

要求：
1. 创建 quant_guard/backtest/funding_fee.py。
2. 实现 calculate_funding_fee(position_notional, funding_rate, side)。
3. 支持 long/short 方向。
4. 支持多次资金费结算累加。
5. 创建 tests/test_funding_fee.py。
6. 不改 Freqtrade 核心源码，先作为独立校验模块。
```

### 验收命令

```bash
pytest tests/test_funding_fee.py
```

### 验收标准

```text
- long / short 正负方向正确。
- 多周期累加正确。
- 边界值测试通过。
```

---

## T2.2 实现强平距离与强平模拟模块

### 任务目标

用标记价格估算强平风险和模拟强平事件。

### Cursor 执行指令

```text
执行 T2.2：实现强平距离与强平模拟模块。

要求：
1. 创建 quant_guard/backtest/liquidation.py。
2. 实现：
   - estimate_liquidation_price()
   - liquidation_distance_pct()
   - should_trigger_liquidation()
3. 输入包括：entry_price、mark_price、side、leverage、margin_mode、maintenance_margin_rate。
4. 先实现保守估算模型，代码注释说明不是交易所精确公式。
5. 创建 tests/test_liquidation.py。
```

### 验收命令

```bash
pytest tests/test_liquidation.py
```

### 验收标准

```text
- 多头价格下跌时强平距离减少。
- 空头价格上涨时强平距离减少。
- 达阈值时能触发模拟强平。
```

---

## T2.3 生成增强回测报告

### 任务目标

在回测结果之外追加资金费、手续费、强平风险、回撤分析。

### Cursor 执行指令

```text
执行 T2.3：实现增强回测报告。

要求：
1. 创建 quant_guard/backtest/report.py。
2. 读取 Freqtrade backtest 结果文件。
3. 输出 Markdown 报告 docs/BACKTEST_VALIDATION.md。
4. 报告至少包含：
   - 总收益
   - 最大回撤
   - 交易次数
   - 手续费估算
   - 资金费估算
   - 强平风险提示
   - 是否允许进入 dry-run 的结论
5. 如果缺少资金费或标记价格数据，必须在报告中标红风险。
```

### 验收标准

```text
- 能生成 Markdown 报告。
- 报告明确说明是否通过 Ph1/Ph2 阶段门禁。
```

---

# PHASE 3：风控系统

## 阶段目标

建立不可绕过的风控模块。实盘前必须完成本阶段全部 P0 项。

---

## T3.1 实现 RiskManager 基础结构

### 任务目标

建立统一风控入口。

### Cursor 执行指令

```text
执行 T3.1：实现 RiskManager 基础结构。

要求：
1. 创建 quant_guard/risk/manager.py。
2. 创建 quant_guard/risk/rules.py。
3. 创建 quant_guard/risk/state.py。
4. 实现 RiskManager.check_order(order_request, account_state, market_state)。
5. 返回 RiskDecision：allow / reject / reduce_only / emergency_stop。
6. 所有 reject 必须带 reason。
7. 创建 tests/test_risk_manager.py。
```

### 验收命令

```bash
pytest tests/test_risk_manager.py
```

---

## T3.2 实现仓位、敞口、杠杆限制

### 任务目标

落实 RISK-01、RISK-02、RISK-03。

### Cursor 执行指令

```text
执行 T3.2：实现仓位、敞口、杠杆硬限制。

要求：
1. 在 RiskManager 中加入：
   - max_single_order_notional
   - max_symbol_notional
   - max_total_notional
   - max_leverage
2. 如果超过限制，必须 reject。
3. 配置来自 risk_config.yaml 或环境变量。
4. 补充单元测试。
```

### 验收标准

```text
- 超过单笔下单量会被拒绝。
- 超过总敞口会被拒绝。
- 超过杠杆上限会被拒绝。
```

---

## T3.3 实现强平距离实时风控

### 任务目标

落实 RISK-04。

### Cursor 执行指令

```text
执行 T3.3：实现强平距离实时风控。

要求：
1. 复用 quant_guard/backtest/liquidation.py 中的强平距离逻辑。
2. 在 RiskManager 中加入 liquidation_distance_threshold。
3. 如果强平距离低于阈值：
   - 禁止加仓
   - 只允许 reduce-only 减仓
   - 触发 alert event
4. 补充单元测试。
```

### 验收标准

```text
- 低于强平距离阈值时禁止开新仓。
- 平仓或减仓允许通过。
```

---

## T3.4 实现最大回撤熔断与每日亏损限额

### 任务目标

落实 RISK-05、RISK-11。

### Cursor 执行指令

```text
执行 T3.4：实现最大回撤熔断与每日亏损限额。

要求：
1. RiskState 记录：
   - equity_high_watermark
   - current_equity
   - daily_start_equity
   - daily_realized_pnl
2. 实现：
   - max_drawdown_stop
   - daily_loss_stop
3. 触发后：
   - 停止开新仓
   - 允许 reduce-only 平仓
   - 写入 kill_switch 状态
4. 补充测试。
```

---

## T3.5 实现 kill switch 与紧急全平接口

### 任务目标

落实 RISK-10。

### Cursor 执行指令

```text
执行 T3.5：实现 kill switch 与紧急全平接口。

要求：
1. 在 RiskManager 中实现 activate_kill_switch(reason)。
2. kill switch 激活后，所有新开仓请求必须 reject。
3. 创建 scripts/emergency_close_all.py。
4. emergency_close_all.py 默认只打印计划，不真实下单。
5. 必须显式传入 --confirm-live 才允许真实执行。
```

### 验收标准

```text
- kill switch 激活后禁止开仓。
- emergency 脚本默认安全，不会误下单。
```

---

# PHASE 4：执行系统

## 阶段目标

建立受风控约束的订单执行层，支持 reduce-only、post-only、幂等订单、重连恢复。

---

## T4.1 实现订单数据模型

### Cursor 执行指令

```text
执行 T4.1：实现订单数据模型。

要求：
1. 创建 quant_guard/execution/order_manager.py。
2. 定义：
   - OrderRequest
   - OrderResult
   - OrderStatus
   - OrderSide
   - OrderType
3. 字段必须包含：
   - symbol
   - side
   - amount
   - price
   - order_type
   - reduce_only
   - post_only
   - client_order_id
4. 创建测试。
```

---

## T4.2 实现 clientOrderId 幂等模块

### Cursor 执行指令

```text
执行 T4.2：实现 clientOrderId 幂等模块。

要求：
1. 创建 quant_guard/execution/idempotency.py。
2. 根据 strategy_id、symbol、side、timestamp_bucket、signal_id 生成 client_order_id。
3. 本地记录已提交订单 ID。
4. 重试时如果 ID 已存在，不重复提交。
5. 创建测试。
```

---

## T4.3 实现 ExecutionEngine

### Cursor 执行指令

```text
执行 T4.3：实现 ExecutionEngine。

要求：
1. 创建 quant_guard/execution/engine.py。
2. ExecutionEngine.submit_order() 必须先调用 RiskManager.check_order()。
3. 风控通过后才调用 exchange client。
4. 支持：
   - market order
   - limit order
   - reduce-only
   - post-only
5. 默认 dry_run=True。
6. live 模式必须要求 explicit_live_confirm=True。
7. 创建 mock 测试，不访问真实交易所。
```

### 验收标准

```text
- 风控 reject 时不会调用交易所。
- dry_run 默认不真实下单。
- live 必须显式确认。
```

---

## T4.4 实现重启状态恢复

### Cursor 执行指令

```text
执行 T4.4：实现重启状态恢复。

要求：
1. ExecutionEngine 启动时调用交易所查询：
   - open orders
   - positions
   - account balance
2. 本地状态以交易所返回为准。
3. 如果本地状态与交易所不一致，记录告警事件。
4. 创建测试，使用 mock exchange 返回不同状态。
```

---

# PHASE 5：监控与 Telegram 控制

## 阶段目标

实现手机端告警、状态查询、启停控制、紧急平仓入口。

---

## T5.1 实现告警事件模型

### Cursor 执行指令

```text
执行 T5.1：实现告警事件模型。

要求：
1. 创建 quant_guard/monitoring/alerts.py。
2. 定义 AlertEvent。
3. 支持级别：INFO、WARNING、CRITICAL。
4. 事件类型包括：
   - order_submitted
   - order_rejected
   - risk_triggered
   - liquidation_warning
   - api_error
   - heartbeat_missed
   - kill_switch_activated
```

---

## T5.2 实现 Telegram Bot

### Cursor 执行指令

```text
执行 T5.2：实现 Telegram Bot。

要求：
1. 创建 quant_guard/monitoring/telegram_bot.py。
2. Token 从环境变量 TELEGRAM_BOT_TOKEN 读取。
3. Chat ID 从环境变量 TELEGRAM_CHAT_ID 读取。
4. 支持发送告警消息。
5. 支持命令：
   - /status
   - /stop
   - /start
   - /risk
   - /emergency_close_all
6. emergency_close_all 命令默认只进入二次确认流程。
7. 不允许单条 Telegram 命令直接实盘全平，必须二次确认。
8. 创建 mock 测试。
```

---

## T5.3 实现心跳监控

### Cursor 执行指令

```text
执行 T5.3：实现进程心跳监控。

要求：
1. 创建 quant_guard/monitoring/heartbeat.py。
2. 定时记录 bot alive 状态。
3. 如果心跳超时，触发 CRITICAL alert。
4. 可被 Docker healthcheck 调用。
```

---

# PHASE 6：Dry-run 模拟盘

## 阶段目标

连续运行模拟盘，验证回测与模拟盘的一致性。

---

## T6.1 创建 dry-run 启动脚本

### Cursor 执行指令

```text
执行 T6.1：创建 dry-run 启动脚本。

要求：
1. 创建 scripts/run_dryrun.sh。
2. 使用 config.dryrun.example.json。
3. 明确 dry_run=true。
4. 启动前检查：
   - 没有真实 live 配置
   - API key 可为空或只读
   - 风控配置存在
```

---

## T6.2 创建 dry-run 验证报告模板

### Cursor 执行指令

```text
执行 T6.2：创建 dry-run 验证报告模板。

要求：
1. 创建 docs/DRYRUN_VALIDATION.md。
2. 报告字段包括：
   - 起止时间
   - 策略版本
   - 交易对
   - 信号数量
   - 模拟成交数量
   - 与同期回测差异
   - 异常记录
   - 是否允许进入 Ph3
```

---

# PHASE 7：小资金实盘前安全门禁

## 阶段目标

在进入任何实盘前，强制完成安全检查。

---

## T7.1 创建 live safety checklist

### Cursor 执行指令

```text
执行 T7.1：创建实盘安全检查清单。

要求：
1. 创建 docs/LIVE_SAFETY_CHECKLIST.md。
2. 必须包含以下检查项：
   - dry-run 连续运行 1-2 周
   - 回测含资金费、手续费、强平风险
   - RiskManager 覆盖所有下单路径
   - kill switch 测试通过
   - emergency close 默认安全
   - Telegram 告警可用
   - API key 禁用提币权限
   - API key 不在代码库
   - reduce-only 平仓可用
   - 重启后状态恢复测试通过
   - 总敞口限制可用
   - 杠杆限制可用
3. 每项必须有：状态、证据、测试命令、负责人确认。
```

---

## T7.2 创建 live 配置保护机制

### Cursor 执行指令

```text
执行 T7.2：创建 live 配置保护机制。

要求：
1. 创建 quant_guard/utils/live_guard.py。
2. 如果 dry_run=false，必须检查：
   - LIVE_TRADING_CONFIRMED=true
   - RISK_CONFIG_LOADED=true
   - TELEGRAM_ENABLED=true
   - KILL_SWITCH_TESTED=true
3. 任一条件不满足，程序必须拒绝启动 live。
4. 创建 tests/test_live_guard.py。
```

---

# PHASE 8：部署与运维

## 阶段目标

容器化部署、自动重启、时间同步、日志与备份。

---

## T8.1 Docker healthcheck 与 restart 策略

### Cursor 执行指令

```text
执行 T8.1：完善 Docker healthcheck 与 restart 策略。

要求：
1. docker-compose.yml 增加 healthcheck。
2. restart 策略使用 unless-stopped。
3. healthcheck 调用 heartbeat。
4. 日志目录映射到 user_data/logs。
```

---

## T8.2 创建部署说明

### Cursor 执行指令

```text
执行 T8.2：创建 VPS 部署说明。

要求：
1. 创建 docs/DEPLOYMENT.md。
2. 包含：
   - 安装 Docker
   - 设置 .env
   - 启动 dry-run
   - 查看日志
   - 停止服务
   - 备份 user_data
   - 恢复流程
3. 明确提醒 live 前必须完成 LIVE_SAFETY_CHECKLIST。
```

---

# 7. 总体验收门禁

## Ph0 通过条件

```text
- 项目结构完整
- Docker 可运行
- Freqtrade 可执行
- EMA 示例策略可回测
```

## Ph1 通过条件

```text
- OKX 数据客户端 mock 测试通过
- FundingRateTrendStrategy 可回测
- walk-forward 验证脚本存在
- 数据质量检查存在
```

## Ph2 通过条件

```text
- 资金费计算测试通过
- 强平距离测试通过
- 增强回测报告可生成
- 报告明确列出资金费与强平风险
```

## Ph3 通过条件

```text
- RiskManager 测试通过
- 仓位限制、杠杆限制、敞口限制可用
- 强平距离风控可用
- 回撤熔断可用
- kill switch 可用
```

## Ph4 通过条件

```text
- ExecutionEngine 所有下单经过 RiskManager
- dry_run 默认安全
- live 必须显式确认
- clientOrderId 幂等测试通过
- 重启恢复测试通过
```

## Ph5 通过条件

```text
- Telegram 告警可用
- /status 可用
- /stop /start 可用
- emergency close 需要二次确认
- heartbeat 可用
```

## Ph6 通过条件

```text
- dry-run 能连续运行
- DRYRUN_VALIDATION.md 有记录
- 与回测差异可解释
```

## Ph7 通过条件

```text
- LIVE_SAFETY_CHECKLIST 全部完成
- live_guard 测试通过
- 用户明确确认进入小资金实盘
```

---

# 8. 每次任务后的日志格式

Cursor 每完成一个任务，必须在 `docs/TASK_LOG.md` 追加：

```markdown
## Tx.x - 任务名称

- 日期：YYYY-MM-DD
- 修改文件：
  - path/to/file.py
- 新增文件：
  - path/to/new_file.py
- 核心变更：
  - ...
- 验收命令：
  ```bash
  pytest ...
  ```
- 验收结果：通过 / 未通过
- 未解决问题：
  - ...
- 下一步建议：
  - Tx.x
```

---

# 9. PROJECT_STATE.md 格式

Cursor 必须维护 `docs/PROJECT_STATE.md`：

```markdown
# Project State

## 当前阶段

Ph0 / Ph1 / Ph2 / Ph3 / Ph4 / Ph5 / Ph6 / Ph7 / Ph8

## 当前已完成任务

- [x] T0.1 初始化仓库结构
- [ ] T0.2 Docker Compose

## 当前禁止事项

- 禁止 live trading
- 禁止 dry_run=false
- 禁止真实下单

## 当前策略

- EmaCrossoverStrategy
- FundingRateTrendStrategy

## 当前风险状态

- Kill switch: inactive
- Max leverage: 未配置 / 已配置
- Max exposure: 未配置 / 已配置

## 下一步任务

T0.2
```

---

# 10. 给用户的 Cursor 使用方法

把本文件放入项目根目录，命名为：

```text
CURSOR_AI_DEVELOPMENT_COMMANDER.md
```

然后在 Cursor 中这样指挥：

```text
请读取 @CURSOR_AI_DEVELOPMENT_COMMANDER.md，严格按照文档执行 T0.1。
只执行 T0.1，不要执行其他任务。
完成后更新 docs/TASK_LOG.md 和 docs/PROJECT_STATE.md。
```

下一步继续：

```text
请读取 @CURSOR_AI_DEVELOPMENT_COMMANDER.md 和 @docs/PROJECT_STATE.md，继续执行 T0.2。
只执行 T0.2，不要跳到后续任务。
```

如果 Cursor 乱改，立即这样纠正：

```text
停止。你偏离了 @CURSOR_AI_DEVELOPMENT_COMMANDER.md。
请回滚无关修改，只保留当前任务允许修改的文件。
重新执行当前任务，并说明改动范围。
```

如果 Cursor 一次性生成太多，立即这样纠正：

```text
不要一次性生成整个系统。
你只能完成当前任务编号。
请按照文档的“允许修改文件”和“验收标准”重新执行。
```

---

# 11. 实盘红线

任何时候，只要以下任意条件不满足，系统不得进入实盘：

```text
- dry-run 未连续运行 1-2 周
- RiskManager 未覆盖所有下单路径
- kill switch 未测试
- emergency close 未测试
- Telegram 告警未测试
- API key 未确认禁用提币权限
- live_guard 未测试通过
- 用户未明确确认小资金实盘
```

---

# 12. 本文档的优先级

如果需求文档、Cursor 临时建议、代码注释、AI 自己的判断发生冲突，优先级如下：

```text
用户明确指令 > 本文档 > 原始需求文档 > Cursor 临时建议 > 代码注释
```

但若用户明确指令要求绕过风控、跳过 dry-run、直接实盘，本项目应提示风险，并要求用户显式确认。

---

# 13. 当前推荐执行顺序

从零开始时，严格按以下命令在 Cursor 中逐条执行：

```text
执行 T0.1
执行 T0.2
执行 T0.3
执行 T0.4
执行 T1.1
执行 T1.2
执行 T1.3
执行 T1.4
执行 T2.1
执行 T2.2
执行 T2.3
执行 T3.1
执行 T3.2
执行 T3.3
执行 T3.4
执行 T3.5
执行 T4.1
执行 T4.2
执行 T4.3
执行 T4.4
执行 T5.1
执行 T5.2
执行 T5.3
执行 T6.1
执行 T6.2
执行 T7.1
执行 T7.2
执行 T8.1
执行 T8.2
```

不得跳过 T3 风控阶段直接进入实盘。

---

# END

本文件是 Cursor 的项目总指挥文件。  
Cursor 每次开发前必须读取，开发后必须更新项目状态与任务日志。
