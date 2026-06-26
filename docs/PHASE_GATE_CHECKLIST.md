# Phase Gate Checklist

> 各阶段门禁检查清单。任一阶段未全部勾选通过，不得进入下一阶段。

## Ph0 - 项目初始化与最小可运行系统

- [x] 项目目录结构完整（按文档第 3 节）
- [x] Python package `quant_guard` 可被 import
- [x] `docs/PROJECT_STATE.md` 与 `docs/TASK_LOG.md` 存在
- [x] T0.2 Docker Compose 可运行（YAML 已校验，docker 命令待目标环境）
- [x] T0.2 Freqtrade 命令可执行（通过官方镜像，待目标环境验证）
- [x] T0.3 EMA 示例策略可被 Freqtrade 识别（语法 OK，待目标环境回测验证）
- [x] T0.3 回测能启动并输出结果（5 币 1 年 Binance 数据验证：1722 笔交易，389 天）
- [x] T0.4 配置模板 JSON 有效，dry_run 默认 true，无真实密钥

**进入 Ph1 条件**：以上全部勾选。（回测链路待目标 Docker 环境，代码层面已就绪）

## Ph1 - 数据层与策略研究

- [x] T1.1 OKX 数据客户端实现，mock 测试通过，public-only 可实例化
- [x] T1.2 数据完整性校验模块实现，12 测试通过
- [ ] T1.3 FundingRateTrendStrategy 可回测，有交易信号，无前视数据
- [ ] T1.4 walk-forward 验证脚本存在，可多窗口运行并输出指标

**进入 Ph2 条件**：样本外 / walk-forward 通过。

## Ph2 - 可信回测增强

- [ ] T2.1 资金费计算模块测试通过（long/short 方向、多周期累加、边界值）
- [ ] T2.2 强平距离 / 强平模拟模块测试通过
- [ ] T2.3 增强回测报告可生成，明确列出资金费与强平风险
- [ ] T2.3 报告明确说明是否通过 Ph1/Ph2 阶段门禁

**进入 Ph3 条件**：回测含资金费、手续费、强平风险，且收益可解释。

## Ph3 - 风控系统（实盘前必须全部完成）

- [ ] T3.1 RiskManager 基础结构，check_order 返回 RiskDecision
- [ ] T3.2 仓位 / 敞口 / 杠杆硬限制（RISK-01/02/03）
- [ ] T3.3 强平距离实时风控（RISK-04）
- [ ] T3.4 最大回撤熔断 + 每日亏损限额（RISK-05/11）
- [ ] T3.5 kill switch + 紧急全平接口（RISK-10）

**进入 Ph4 条件**：P0 风控全部测试通过。

## Ph4 - 执行系统

- [ ] T4.1 订单数据模型定义完整
- [ ] T4.2 clientOrderId 幂等模块测试通过
- [ ] T4.3 ExecutionEngine 所有下单经过 RiskManager，dry_run 默认安全，live 需显式确认
- [ ] T4.4 重启状态恢复测试通过

**进入 Ph5 条件**：执行层闭环、幂等、恢复全部验证。

## Ph5 - 监控与 Telegram 控制

- [ ] T5.1 告警事件模型定义完整
- [ ] T5.2 Telegram Bot：/status /stop /start /risk /emergency_close_all 可用，紧急平仓需二次确认
- [ ] T5.3 心跳监控可用，可被 Docker healthcheck 调用

**进入 Ph6 条件**：告警 / 控制 / 心跳全部可用。

## Ph6 - Dry-run 模拟盘

- [ ] T6.1 dry-run 启动脚本完成，启动前安全检查通过
- [ ] T6.2 DRYRUN_VALIDATION.md 模板就绪
- [ ] 连续运行 1-2 周且无重大偏离

**进入 Ph7 条件**：dry-run 连续运行 1-2 周，与回测差异可解释。

## Ph7 - 小资金实盘前安全门禁

- [ ] T7.1 LIVE_SAFETY_CHECKLIST 全部检查项完成
- [ ] T7.2 live_guard 测试通过，缺任一环境变量拒绝启动
- [ ] 用户明确书面确认进入小资金实盘

**进入实盘条件**：以上全部勾选 + 用户明确确认。

## Ph8 - 部署与运维

- [ ] T8.1 Docker healthcheck + restart 策略
- [ ] T8.2 VPS 部署说明 docs/DEPLOYMENT.md
