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
    api.get<string[]>('/backtest/list').then((r) => r.data),
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
}

export default api
