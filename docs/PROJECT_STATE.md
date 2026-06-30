# Project State

> 本文件反映项目当前真实状态（最后更新：2026-06-30）。

## 当前阶段

Ph0–Ph5 ✅ · Ph6 dry-run（Web 控制台已接入）· Ph7 实盘门禁（代码就绪，未启用）

## 代码规模

| 模块 | 约行数 |
|---|---|
| quant_guard 后端 | 5,500+ |
| frontend React | 2,900+ |
| 策略 + 脚本 + 测试 | 3,900+ |
| **源码合计** | **~12,300** |

- API 路由：**40+**
- pytest：**140+**

## 已完成功能

### 后端核心
- OKX 客户端（行情 / 持仓 / 历史 / 平仓下单）
- RiskManager + ExecutionEngine（下单必经风控）
- **ControlService**：Kill Switch 停 Bot + 紧急全平
- Freqtrade 回测 + dry-run 进程管理
- K 线复盘、持仓统计、权益曲线

### Web 前端（8 页）
- 仪表盘、回测、策略、交易所、持仓复盘、持仓分析、控制台、告警
- 单端口 `scripts/start_web.sh` → http://localhost:8000

### 数据
- Binance + OKX 双轨 K 线下载（`scripts/download_klines.sh`）
- 本地 feather 格式，Web 回测用 Binance 数据

## 测试统计

```bash
.venv/bin/pytest   # 140 tests
```

## 关键参数

| 参数 | 值 |
|---|---|
| 交易所 | OKX |
| 持仓模式 | 双向（long_short） |
| 最高杠杆 | 5x |
| 小资金实盘 | ≤ 1000 USDT |

## 已知限制

1. **Freqtrade 下单路径**尚未挂接 `ExecutionEngine`（Web 紧急平仓走 OKX 直连）
2. **回测数据**（Binance）与 **dry-run 行情**（OKX）来源不同
3. 实盘需完成 `docs/LIVE_SAFETY_CHECKLIST.md` + `LIVE_TRADING_CONFIRMED=true`

## 下一步

- [ ] Ph6 完整 dry-run 验收报告（`docs/DRYRUN_VALIDATION.md`）
- [ ] Freqtrade 自定义下单钩子接入 RiskManager
- [ ] 统一账户模式与 `.env` 配置对齐
- [ ] Telegram 告警挂到运行流程
