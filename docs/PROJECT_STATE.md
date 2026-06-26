# Project State

> 本文件由 Cursor 在每个任务完成后维护，反映项目当前真实状态。

## 当前阶段

Ph0 已完成（代码层面；回测链路待目标 Docker 环境验证） → 准备进入 Ph1

## 当前已完成任务

- [x] T0.1 初始化仓库结构
- [x] T0.2 Docker Compose 与 Freqtrade 基础环境
- [x] T0.3 创建 Freqtrade 示例策略（EmaCrossoverStrategy）
- [x] T0.4 创建配置模板（example / dryrun / live）
- [x] T1.1 实现 OKX 数据客户端（mock 测试通过）
- [x] T1.2 实现数据完整性校验（12 测试通过）
- [x] T1.3 实现 FundingRateTrendStrategy（EMA+ATR+资金费过滤）
- [x] F0.1 前端骨架（React+Vite+AntD+Recharts+4页面+路由）
- [x] F0.2 FastAPI 后端骨架（17 路由，TestClient 全通过）

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

## 当前禁止事项

- 禁止 live trading
- 禁止 dry_run=false
- 禁止真实下单
- 禁止把 API Key / Secret / Passphrase 写入代码库
- 禁止策略直接调用交易所下单接口
- 禁止绕过 RiskManager

## 当前策略

- EmaCrossoverStrategy（T0.3 已实现，EMA20/EMA50 交叉）
- FundingRateTrendStrategy（T1.3 已实现，EMA+ATR+资金费过滤）

## 当前风险状态

- Kill switch: 未实现（待 T3.5）
- Max leverage: 5x（决策值，待 T3.2 落地）
- Max exposure: 1000 USDT（决策值，待 T3.2 落地）

## 环境备注

- 本机未安装 Docker Desktop（IDE 的 Docker 扩展仅为 GUI，底层需 Docker Engine）
- Freqtrade 已通过 `pip install freqtrade` 本地安装（v2026.5.1），可直接用 `freqtrade` 命令
- 本机无法访问 OKX/binance/bybit/kraken API（网络限制），仅 gate.io API 可达
- **Binance 公开数据站 data.binance.vision 可达**，已通过月线包下载 5 币 1 年 15m 数据
- **5 币 1 年回测已验证通过**：用 Binance 数据 + gate 配置跑 EmaCrossoverStrategy，
  389 天，1722 笔交易，结果正常输出
- 正式 OKX 数据下载与回测需在可访问 OKX 的环境（VPS/配代理）执行

## 下一步任务

T1.4 walk-forward 验证脚本 / 前端细化（告警实时推送、回测 API 接入真实结果）
