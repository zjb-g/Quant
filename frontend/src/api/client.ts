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

export interface PositionHistory {
  position_id: string
  symbol: string
  side: 'long' | 'short'
  leverage: number
  margin_mode: string
  open_avg_price: number
  close_avg_price: number
  close_size: number
  pnl: number
  realized_pnl: number
  pnl_ratio: number
  fee: number
  funding_fee: number
  close_type: string
  open_time: string
  close_time: string
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

export interface BacktestJob {
  id: string
  strategy: string
  timerange: string
  status: 'pending' | 'running' | 'done' | 'error'
  result_id?: string | null
  error?: string | null
  started_at?: string
  finished_at?: string
}

export interface BotStatus {
  running: boolean
  pid?: number | null
  strategy: string
  dry_run: boolean
  started_at?: string | null
  last_error?: string | null
  log_tail: string[]
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

export interface ChartSymbolInfo {
  symbol: string
  base: string
  source: string
  intervals: string[]
}

export interface ChartCandle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface ChartMarker {
  position_id: string
  marker_type: 'entry' | 'exit'
  time: number
  price: number
  side: string
  pnl: number
  leverage: number
  close_type: string
  label: string
}

export interface ChartReviewData {
  symbol: string
  interval: string
  data_source: string
  candles: ChartCandle[]
  markers: ChartMarker[]
  positions: PositionHistory[]
  total_pnl: number
}

export type ChartMarkerMode = 'all' | 'time_range' | 'selected' | 'none'

export interface ChartReviewOptions {
  limit?: number
  positionIds?: string[]
  closeTimes?: string[]
  startTime?: string
  endTime?: string
  markerMode?: ChartMarkerMode
}

export interface PositionHistoryQuery {
  all?: boolean
  limit?: number
  symbol?: string
  side?: string
  closeType?: string
  startTime?: string
  endTime?: string
  positionIds?: string
  sortBy?: 'close_time' | 'open_time' | 'pnl' | 'pnl_ratio' | 'leverage'
  order?: 'asc' | 'desc'
  minPnl?: number
  maxPnl?: number
}

export interface TradeBucketStats {
  label: string
  count: number
  wins: number
  losses: number
  win_rate: number
  total_pnl: number
  avg_pnl: number
}

export interface TradeAnalysisStats {
  total_trades: number
  wins: number
  losses: number
  win_rate: number
  total_pnl: number
  avg_pnl: number
  avg_win: number
  avg_loss: number
  profit_factor: number
  max_win: number
  max_loss: number
  total_fee: number
  total_funding_fee: number
  avg_holding_hours: number
  by_side: TradeBucketStats[]
  by_leverage: TradeBucketStats[]
  by_holding: TradeBucketStats[]
  by_close_type: TradeBucketStats[]
  by_symbol: TradeBucketStats[]
}

export interface TradeAnalysisResponse {
  stats: TradeAnalysisStats
  filtered_count: number
  total_count: number
}

export interface AiTradeAnalysisResponse {
  analysis: string
  stats: TradeAnalysisStats
  trade_count: number
}

// ---------- API 函数 ----------

export const apiClient = {
  // 仪表盘
  getSystemStatus: () => api.get<SystemStatus>('/status').then((r) => r.data),
  getPositions: () => api.get<Position[]>('/positions', { timeout: 8000 }).then((r) => r.data),
  getPositionsHistory: (limit = 50, all = false) =>
    api
      .get<PositionHistory[]>(
        all ? '/positions/history?all=true' : `/positions/history?limit=${limit}`,
      )
      .then((r) => r.data),
  getEquityCurve: (days = 30) =>
    api.get<EquityPoint[]>(`/equity?days=${days}`).then((r) => r.data),
  getRiskState: () => api.get<RiskState>('/risk/state').then((r) => r.data),

  // 回测
  getBacktestList: () =>
    api.get<{id: string; strategy: string; timestamp: string}[]>('/backtest/list').then((r) => r.data),
  getBacktestDefaultTimerange: () =>
    api.get<{timerange: string}>('/backtest/timerange-default').then((r) => r.data),
  runBacktest: (strategy: string, timerange: string, asyncRun = true) =>
    api.post<BacktestJob>(
      '/backtest/run',
      { strategy, timerange, async_run: asyncRun },
      { timeout: 600000 },
    ).then((r) => r.data),
  getBacktestJob: (jobId: string) =>
    api.get<BacktestJob>(`/backtest/jobs/${jobId}`).then((r) => r.data),
  getBacktestResult: (id: string) =>
    api
      .get<{ summary: BacktestSummary; trades: BacktestTrade[] }>(
        `/backtest/${id}`,
      )
      .then((r) => r.data),

  // 控制
  startBot: (strategy = 'EmaCrossoverStrategy') =>
    api.post('/control/start', { strategy }).then((r) => r.data),
  stopBot: () => api.post('/control/stop').then((r) => r.data),
  getBotStatus: () => api.get<BotStatus>('/control/status').then((r) => r.data),
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
    api.post('/ai/generate-strategy', { description, filename: filename || '' }, { timeout: 180000 }).then((r) => r.data),
  aiRefineStrategy: (code: string, feedback: string) =>
    api.post('/ai/refine-strategy', { code, feedback }, { timeout: 180000 }).then((r) => r.data),

  // 交易所连接
  getExchangeStatus: () =>
    api.get<{connected: boolean; exchange: string; error: string; account_mode: string}>('/exchange/status').then((r) => r.data),
  testExchange: (vars: Record<string, string>) =>
    api.post('/exchange/test', { vars }).then((r) => r.data),
  getExchangeBalance: () =>
    api.get<{total: number; free: number; used: number; currency: string}>('/exchange/balance').then((r) => r.data),
  getExchangePositions: () =>
    api.get<Position[]>('/exchange/positions').then((r) => r.data),
  getExchangePositionsHistory: (limit = 50, all = false) =>
    api
      .get<PositionHistory[]>(
        all
          ? '/exchange/positions/history?all=true'
          : `/exchange/positions/history?limit=${limit}`,
      )
      .then((r) => r.data),
  getExchangeTrades: (limit = 100) =>
    api.get<HistoricalTrade[]>(`/exchange/trades?limit=${limit}`).then((r) => r.data),
  getExchangeOrders: () =>
    api.get('/exchange/orders').then((r) => r.data),
  getEnvStatus: () =>
    api.get<Record<string, boolean>>('/env').then((r) => r.data),

  // 持仓复盘 K 线
  getChartSymbols: () =>
    api.get<ChartSymbolInfo[]>('/chart/symbols').then((r) => r.data),
  getChartReview: (symbol: string, interval = '15m', opts: ChartReviewOptions = {}) => {
    const params = new URLSearchParams({
      symbol,
      interval,
      limit: String(opts.limit ?? 3000),
      marker_mode: opts.markerMode ?? 'all',
    })
    if (opts.startTime) params.set('start_time', opts.startTime)
    if (opts.endTime) params.set('end_time', opts.endTime)
    if (opts.positionIds?.length) params.set('position_ids', opts.positionIds.join(','))
    if (opts.closeTimes?.length) params.set('close_times', opts.closeTimes.join(','))
    return api.get<ChartReviewData>(`/chart/review?${params}`, { timeout: 120000 }).then((r) => r.data)
  },

  queryPositionsHistory: (query: PositionHistoryQuery = {}) => {
    const params = new URLSearchParams()
    if (query.all) params.set('all', 'true')
    if (query.limit) params.set('limit', String(query.limit))
    if (query.symbol) params.set('symbol', query.symbol)
    if (query.side) params.set('side', query.side)
    if (query.closeType) params.set('close_type', query.closeType)
    if (query.startTime) params.set('start_time', query.startTime)
    if (query.endTime) params.set('end_time', query.endTime)
    if (query.positionIds) params.set('position_ids', query.positionIds)
    if (query.sortBy) params.set('sort_by', query.sortBy)
    if (query.order) params.set('order', query.order)
    if (query.minPnl != null) params.set('min_pnl', String(query.minPnl))
    if (query.maxPnl != null) params.set('max_pnl', String(query.maxPnl))
    return api.get<PositionHistory[]>(`/positions/history?${params}`, { timeout: 60000 }).then((r) => r.data)
  },

  analyzePositionsHistory: (opts: { symbol?: string; side?: string; startTime?: string; endTime?: string } = {}) => {
    const params = new URLSearchParams({ all: 'true' })
    if (opts.symbol) params.set('symbol', opts.symbol)
    if (opts.side) params.set('side', opts.side)
    if (opts.startTime) params.set('start_time', opts.startTime)
    if (opts.endTime) params.set('end_time', opts.endTime)
    return api.get<TradeAnalysisResponse>(`/positions/history/analyze?${params}`, { timeout: 60000 }).then((r) => r.data)
  },

  aiAnalyzeTrades: (opts: { symbol?: string; side?: string; startTime?: string; endTime?: string } = {}) =>
    api.post<AiTradeAnalysisResponse>('/ai/analyze-trades', {
      symbol: opts.symbol ?? null,
      side: opts.side ?? null,
      start_time: opts.startTime ?? null,
      end_time: opts.endTime ?? null,
    }, { timeout: 180000 }).then((r) => r.data),
}

// ---------- 额外类型 ----------

export interface StrategyInfo {
  id: string
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
