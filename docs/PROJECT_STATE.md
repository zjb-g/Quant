# Project State

> 本文件由 Cursor 在每个任务完成后维护，反映项目当前真实状态。

## 当前阶段

Ph0 ✅ → Ph1 ✅ → Ph2 ✅ → Ph3 ✅ → Ph4 ✅ → Ph5 ✅ → 待 Ph6 dry-run 运行

## 当前已完成任务

### 后端核心（按 COMMANDER 文档）
- [x] T0.1 初始化仓库结构
- [x] T0.2 Docker Compose 与 Freqtrade 基础环境
- [x] T0.3 创建 Freqtrade 示例策略（EmaCrossoverStrategy）
- [x] T0.4 创建配置模板（example / dryrun / live）
- [x] T1.1 实现 OKX 数据客户端（15 mock 测试通过）
- [x] T1.2 实现数据完整性校验（12 测试通过）
- [x] T1.3 实现 FundingRateTrendStrategy + RSI + Bollinger（4 策略）
- [x] T1.4 walk-forward 验证脚本
- [x] T2.1 资金费计算模块（19 测试通过）
- [x] T2.2 强平距离与强平模拟（26 测试通过）
- [x] T2.3 增强回测报告生成
- [x] T3.1 RiskManager 基础结构（25 测试通过）
- [x] T3.2 仓位/敞口/杠杆硬限制（RISK-01/02/03）
- [x] T3.3 强平距离实时风控（RISK-04）
- [x] T3.4 回撤熔断 + 每日亏损限额（RISK-05/11）
- [x] T3.5 kill switch + 紧急全平（RISK-10）
- [x] T4.1 订单数据模型（OrderRequest/OrderResult/OrderStatus）
- [x] T4.2 clientOrderId 幂等模块
- [x] T4.3 ExecutionEngine（所有下单经过 RiskManager）
- [x] T4.4 重启状态恢复（接口已定义）
- [x] T5.1 告警事件模型（AlertEvent/AlertManager）
- [x] T5.2 Telegram Bot（5 命令 + 二次确认）
- [x] T5.3 心跳监控（Docker healthcheck）

### 前端 + API
- [x] F0.1 React+Vite+AntD+Recharts 前端骨架（4 页面）
- [x] F0.2 FastAPI 后端（17 路由，TestClient 全通过）
- [x] F0.3 仪表盘页面
- [x] F0.4 回测分析页面（4 策略结果可查看）
- [x] F0.5 控制台页面（启停/Kill Switch/紧急全平/风控参数）
- [x] 告警页面

### 数据与回测
- [x] Binance 公开数据下载脚本（月线包+日线包）
- [x] 5 币 1 年 15m 数据（每币 37440 根）
- [x] 4 策略 1 年回测完成

## 测试统计

**111 个测试全部通过**：
- test_okx_client: 15
- test_data_quality: 12
- test_funding_fee: 19
- test_liquidation: 26
- test_risk_manager: 25
- test_execution_engine: 14

## 项目关键参数（决策锁定）

| 参数 | 值 |
|---|---|
| 交易所 | OKX |
| 账户模式 | 统一账户（Unified） |
| 持仓模式 | 双向持仓（long_short，支持对冲） |
| 最高杠杆 | 5x |
| 交易品种 | BTC / ETH / SOL / BNB / XRP（USDT 永续） |
| 策略主时间框架 | 15m |
| 小资金实盘规模 | ≤ 1000 USDT |
| 资金费结算频率 | 每 8h（00/08/16 UTC） |

## 当前策略

- EmaCrossoverStrategy（EMA20/EMA50 交叉）
- FundingRateTrendStrategy（EMA+ATR+资金费过滤）
- RsiReversalStrategy（RSI 超买超卖反转）
- BollingerBreakoutStrategy（布林带突破）

## 当前风控状态

- Kill switch: ✅ 已实现（T3.5）
- Max leverage: ✅ 5x（T3.2 已落地）
- Max exposure: ✅ 1000 USDT（T3.2 已落地）
- 单笔上限: ✅ 200 USDT（RISK-01）
- 单币敞口: ✅ 300 USDT（RISK-02）
- 回撤熔断: ✅ 15%（RISK-05）
- 日亏限额: ✅ 5%（RISK-11）
- 强平距离: ✅ 10%（RISK-04）

## 环境备注

- 本机未安装 Docker Desktop
- Freqtrade 已通过 pip 安装（v2026.5.1）
- 本机仅 gate.io API 可达，Binance 公开数据站可达
- 正式 OKX 部署需在 VPS 或配代理环境执行

## 下一步任务

- T6.1 dry-run 启动脚本 + 启动前安全检查
- T6.2 DRYRUN_VALIDATION.md 验证报告模板
- T7.1 LIVE_SAFETY_CHECKLIST
- T7.2 live_guard 模块
- T8.1 Docker healthcheck + restart 策略
- T8.2 VPS 部署说明
