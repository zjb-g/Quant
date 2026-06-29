import axios from 'axios'

// API 客户端：统一基础路径 /api（开发时由 vite proxy 转发到 FastAPI）
const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// ---------- 类型定义 ----------

export interface SystemStatus {
  bot_running: boolean
  dry_run: boolean
  strategy: string
  exchange: string
  uptime_seconds: number
  current_time: string
}

export interface Position {
  symbol: string
  side: 'long' | 'short'
  contracts: number
  entry_price: number
  mark_price: number
  leverage: number
  unrealized_pnl: number
  liquidation_price: number | null
}

export interface EquityPoint {
  timestamp: string
  equity: number
  drawdown_pct: number
}

export interface RiskState {
  kill_switch: boolean
  kill_switch_reason: string | null
  max_leverage: number
  max_total_notional: number
  current_total_notional: number
  equity_high_watermark: number
  current_equity: number
  max_drawdown_pct: number
  daily_start_equity: number
  daily_loss_pct: number
  daily_loss_limit_pct: number
}

export interface AlertEvent {
  id: string
  timestamp: string
  level: 'INFO' | 'WARNING' | 'CRITICAL'
  type: string
  message: string
}

export interface BacktestSummary {
  strategy: string
  timerange: string
  total_trades: number
  total_profit_pct: number
  max_drawdown_pct: number
  win_rate: number
  avg_duration: string
  sharpe: number
  sortino: number
}

export interface BacktestTrade {
  pair: string
  open_date: string
  close_date: string
  side: 'long' | 'short'
  open_rate: number
  close_rate: number
  profit_pct: number
  profit_abs: number
  exit_reason: string
}

export interface RiskConfig {
  max_single_order_notional: number
  max_symbol_notional: number
  max_total_notional: number
  max_leverage: number
  max_drawdown_stop_pct: number
  daily_loss_stop_pct: number
  liquidation_distance_pct: number
}

// ---------- API 函数 ----------

export const apiClient = {
  // 仪表盘
  getSystemStatus: () => api.get<SystemStatus>('/status').then((r) => r.data),
  getPositions: () => api.get<Position[]>('/positions').then((r) => r.data),
  getEquityCurve: (days = 30) =>
    api.get<EquityPoint[]>(`/equity?days=${days}`).then((r) => r.data),
  getRiskState: () => api.get<RiskState>('/risk/state').then((r) => r.data),

  // 回测
  getBacktestList: () =>
    api.get<{id: string; strategy: string; timestamp: string}[]>('/backtest/list').then((r) => r.data),
  getBacktestResult: (id: string) =>
    api
      .get<{ summary: BacktestSummary; trades: BacktestTrade[] }>(
        `/backtest/${id}`,
      )
      .then((r) => r.data),

  // 控制
  startBot: () => api.post('/control/start').then((r) => r.data),
  stopBot: () => api.post('/control/stop').then((r) => r.data),
  activateKillSwitch: (reason: string) =>
    api.post('/control/kill-switch', { reason }).then((r) => r.data),
  emergencyCloseAll: (confirm: boolean) =>
    api.post('/control/emergency-close', { confirm }).then((r) => r.data),
  getRiskConfig: () => api.get<RiskConfig>('/risk/config').then((r) => r.data),
  updateRiskConfig: (config: Partial<RiskConfig>) =>
    api.put('/risk/config', config).then((r) => r.data),

  // 告警
  getAlerts: (limit = 100) =>
    api.get<AlertEvent[]>(`/alerts?limit=${limit}`).then((r) => r.data),

  // 策略管理
  getStrategies: () =>
    api.get<StrategyInfo[]>('/strategies').then((r) => r.data),
  getStrategyCode: (filename: string) =>
    api.get<{filename: string; code: string}>(`/strategies/${filename}`).then((r) => r.data),
  saveStrategy: (filename: string, code: string) =>
    api.post('/strategies', { filename, code }).then((r) => r.data),
  deleteStrategy: (filename: string) =>
    api.delete(`/strategies/${filename}`).then((r) => r.data),

  // AI 策略生成
  aiStatus: () =>
    api.get<{configured: boolean; model: string}>('/ai/status').then((r) => r.data),
  aiGenerateStrategy: (description: string, filename?: string) =>
    api.post('/ai/generate-strategy', { description, filename: filename || '' }).then((r) => r.data),
  aiRefineStrategy: (code: string, feedback: string) =>
    api.post('/ai/refine-strategy', { code, feedback }).then((r) => r.data),

  // 交易所连接
  getExchangeStatus: () =>
    api.get<{connected: boolean; exchange: string; error: string; account_mode: string}>('/exchange/status').then((r) => r.data),
  testExchange: (vars: Record<string, string>) =>
    api.post('/exchange/test', { vars }).then((r) => r.data),
  getExchangeBalance: () =>
    api.get<{total: number; free: number; used: number; currency: string}>('/exchange/balance').then((r) => r.data),
  getExchangePositions: () =>
    api.get<Position[]>('/exchange/positions').then((r) => r.data),
  getExchangeTrades: (limit = 100) =>
    api.get<HistoricalTrade[]>(`/exchange/trades?limit=${limit}`).then((r) => r.data),
  getExchangeOrders: () =>
    api.get('/exchange/orders').then((r) => r.data),
  getEnvStatus: () =>
    api.get<Record<string, boolean>>('/env').then((r) => r.data),
}

// ---------- 额外类型 ----------

export interface StrategyInfo {
  filename: string
  name: string
  description: string
  size: number
  has_errors: boolean
  error_msg: string
}

export interface HistoricalTrade {
  id: string
  timestamp: string
  symbol: string
  side: string
  amount: number
  price: number
  fee: number
  pnl: number
}
