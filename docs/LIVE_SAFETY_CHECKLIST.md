# Live Safety Checklist

> 进入小资金实盘前必须全部完成。每项需有状态、证据、测试命令、负责人确认。
> 任一未通过，系统不得进入实盘。

## 1. Dry-run 验证

| # | 检查项 | 状态 | 证据 | 测试命令 | 确认人 |
|---|---|---|---|---|---|
| 1.1 | dry-run 连续运行 1-2 周 | ☐ | 运行日志 + DRYRUN_VALIDATION.md | `cat docs/DRYRUN_VALIDATION.md` | |
| 1.2 | dry-run 与回测差异可解释 | ☐ | 差异分析报告 | - | |

## 2. 回测可信度

| # | 检查项 | 状态 | 证据 | 测试命令 | 确认人 |
|---|---|---|---|---|---|
| 2.1 | 回测含资金费 | ☐ | BACKTEST_VALIDATION.md | `python -c "from quant_guard.backtest.funding_fee import calculate_funding_fee"` | |
| 2.2 | 回测含手续费 | ☐ | 回测报告 | - | |
| 2.3 | 回测含强平风险 | ☐ | BACKTEST_VALIDATION.md | `python -c "from quant_guard.backtest.liquidation import estimate_liquidation_price"` | |
| 2.4 | walk-forward 验证通过 | ☐ | walk-forward 报告 | `python scripts/walk_forward_backtest.py --strategy X` | |

## 3. 风控系统

| # | 检查项 | 状态 | 证据 | 测试命令 | 确认人 |
|---|---|---|---|---|---|
| 3.1 | RiskManager 覆盖所有下单路径 | ☐ | ExecutionEngine 代码审查 | `pytest tests/test_risk_manager.py` | |
| 3.2 | 仓位限制可用（RISK-01/02） | ☐ | 测试通过 | `pytest tests/test_risk_manager.py -k "notional or exposure"` | |
| 3.3 | 杠杆限制可用（RISK-03） | ☐ | 测试通过 | `pytest tests/test_risk_manager.py -k leverage` | |
| 3.4 | 强平距离风控可用（RISK-04） | ☐ | 测试通过 | `pytest tests/test_risk_manager.py -k liquidation` | |
| 3.5 | 回撤熔断可用（RISK-05） | ☐ | 测试通过 | `pytest tests/test_risk_manager.py -k drawdown` | |
| 3.6 | 每日亏损限额可用（RISK-11） | ☐ | 测试通过 | `pytest tests/test_risk_manager.py -k daily_loss` | |
| 3.7 | kill switch 测试通过 | ☐ | 测试通过 | `pytest tests/test_risk_manager.py -k kill_switch` | |
| 3.8 | emergency close 默认安全 | ☐ | 脚本需 --confirm-live | `python scripts/emergency_close_all.py` | |

## 4. 执行系统

| # | 检查项 | 状态 | 证据 | 测试命令 | 确认人 |
|---|---|---|---|---|---|
| 4.1 | clientOrderId 幂等测试通过 | ☐ | 测试通过 | `pytest tests/test_execution_engine.py -k duplicate` | |
| 4.2 | 重启后状态恢复测试通过 | ☐ | 测试通过 | `pytest tests/test_execution_engine.py` | |
| 4.3 | reduce-only 平仓可用 | ☐ | 测试通过 | `pytest tests/test_execution_engine.py -k reduce_only` | |

## 5. 监控与告警

| # | 检查项 | 状态 | 证据 | 测试命令 | 确认人 |
|---|---|---|---|---|---|
| 5.1 | Telegram 告警可用 | ☐ | 收到测试消息 | - | |
| 5.2 | /status 命令可用 | ☐ | Telegram 回复正常 | - | |
| 5.3 | /stop /start 命令可用 | ☐ | Telegram 回复正常 | - | |
| 5.4 | emergency_close 需二次确认 | ☐ | Telegram 回复正常 | - | |
| 5.5 | heartbeat 可用 | ☐ | 心跳状态正常 | `python -c "from quant_guard.monitoring.heartbeat import HeartbeatMonitor; print('OK')"` | |

## 6. API Key 安全

| # | 检查项 | 状态 | 证据 | 测试命令 | 确认人 |
|---|---|---|---|---|---|
| 6.1 | API key 禁用提币权限 | ☐ | OKX 后台截图 | - | |
| 6.2 | API key 不在代码库 | ☐ | git log 审查 | `git log --all -p | grep -i "api_key\|secret\|passphrase"` | |
| 6.3 | API key 从 .env 读取 | ☐ | 代码审查 | - | |
| 6.4 | 无资金划转/提币逻辑 | ☐ | 代码审查 | - | |

## 7. live_guard

| # | 检查项 | 状态 | 证据 | 测试命令 | 确认人 |
|---|---|---|---|---|---|
| 7.1 | live_guard 测试通过 | ☐ | 测试通过 | `pytest tests/test_live_guard.py` | |
| 7.2 | 缺环境变量拒绝启动 | ☐ | 测试通过 | `pytest tests/test_live_guard.py -k reject` | |

## 8. 用户确认

| # | 检查项 | 状态 | 日期 | 确认人 |
|---|---|---|---|---|
| 8.1 | 用户明确书面确认进入小资金实盘 | ☐ | | |
| 8.2 | 实盘规模 ≤ 1000 USDT 确认 | ☐ | | |

---

## 最终结论

- [ ] 以上全部检查项通过
- [ ] 用户已明确书面确认

**允许进入小资金实盘**：✅ 是 / ❌ 否

签字：____________ 日期：____________
