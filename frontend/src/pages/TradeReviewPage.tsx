import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Card, Select, Space, Button, Table, Tag, Statistic, Row, Col, Spin, message, Alert,
  Segmented, DatePicker, Radio,
} from 'antd'
import { ReloadOutlined, LineChartOutlined } from '@ant-design/icons'
import type { TableProps } from 'antd'
import type { Dayjs } from 'dayjs'
import {
  apiClient,
  type ChartMarkerMode,
  type ChartReviewData,
  type ChartSymbolInfo,
  type PositionHistory,
} from '../api/client'

type ChartLib = typeof import('lightweight-charts')
type IChartApi = import('lightweight-charts').IChartApi
type UTCTimestamp = import('lightweight-charts').UTCTimestamp

const { RangePicker } = DatePicker

const CLOSE_TYPE_LABELS: Record<string, string> = {
  partial: '部分平仓',
  full: '完全平仓',
  liquidation: '强平',
  forced_reduction: '强减',
  adl: 'ADL',
  unknown: '未知',
}

const INTERVAL_ORDER = ['1m', '5m', '15m', '1h', '4h', '12h', '1d', '1w', '1M']

function inferPriceFormat(candles: ChartReviewData['candles']) {
  let minPrice = Infinity
  for (const c of candles) {
    minPrice = Math.min(minPrice, c.low, c.open, c.close)
  }
  if (!Number.isFinite(minPrice) || minPrice <= 0) {
    return { type: 'price' as const, precision: 2, minMove: 0.01 }
  }
  if (minPrice >= 1) return { type: 'price' as const, precision: 2, minMove: 0.01 }
  if (minPrice >= 0.01) return { type: 'price' as const, precision: 4, minMove: 0.0001 }
  const exp = Math.floor(Math.log10(minPrice))
  const precision = Math.min(12, Math.max(4, -exp + 2))
  const minMove = 10 ** -precision
  return { type: 'price' as const, precision, minMove }
}

function snapToNearestCandleSec(markerMs: number, candleSecs: number[]): UTCTimestamp {
  const t = Math.floor(markerMs / 1000)
  if (!candleSecs.length) return t as UTCTimestamp

  let lo = 0
  let hi = candleSecs.length - 1
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2)
    if (candleSecs[mid] < t) lo = mid + 1
    else hi = mid
  }

  let best = candleSecs[lo]
  if (lo > 0) {
    const prev = candleSecs[lo - 1]
    if (Math.abs(prev - t) <= Math.abs(best - t)) best = prev
  }
  return best as UTCTimestamp
}

function pickInterval(current: string, available: string[]) {
  if (available.includes(current)) return current
  if (available.includes('15m')) return '15m'
  if (available.includes('1h')) return '1h'
  if (available.includes('1d')) return '1d'
  return available[0] ?? '15m'
}

function positionRowKey(p: PositionHistory) {
  return `${p.position_id}::${p.close_time}`
}

export default function TradeReviewPage() {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartApi = useRef<IChartApi | null>(null)
  const [symbols, setSymbols] = useState<ChartSymbolInfo[]>([])
  const [symbol, setSymbol] = useState('ETH-USDT-SWAP')
  const [tableSymbol, setTableSymbol] = useState<string | undefined>(undefined)
  const [timeframe, setTimeframe] = useState('15m')
  const [loading, setLoading] = useState(false)
  const [tableLoading, setTableLoading] = useState(false)
  const [data, setData] = useState<ChartReviewData | null>(null)
  const [tablePositions, setTablePositions] = useState<PositionHistory[]>([])
  const [ready, setReady] = useState(false)

  const [markerMode, setMarkerMode] = useState<ChartMarkerMode>('all')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [chartTimeRange, setChartTimeRange] = useState<[Dayjs, Dayjs] | null>(null)

  const [tableTimeRange, setTableTimeRange] = useState<[Dayjs, Dayjs] | null>(null)
  const [tableSortBy, setTableSortBy] = useState<'close_time' | 'pnl'>('close_time')
  const [tableOrder, setTableOrder] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    apiClient.getChartSymbols()
      .then((list) => {
        setSymbols(list)
        if (list.length && !list.find((s) => s.symbol === symbol)) {
          const first = list[0]
          setSymbol(first.symbol)
          setTimeframe(pickInterval('15m', first.intervals))
        }
        setReady(true)
      })
      .catch(() => message.error('无法加载币种列表，请确认后端 API 已启动（端口 8000）'))
  }, [])

  const chartLib = useRef<ChartLib | null>(null)
  const loadId = useRef(0)
  const markersApi = useRef<ReturnType<NonNullable<ChartLib>['createSeriesMarkers']> | null>(null)

  const destroyChart = useCallback(() => {
    markersApi.current = null
    if (chartApi.current) {
      chartApi.current.remove()
      chartApi.current = null
    }
  }, [])

  const renderChart = useCallback(async (review: ChartReviewData, fitToMarkers: boolean) => {
    if (!chartRef.current) return
    if (!review.candles.length) {
      message.warning('该币种暂无 K 线数据')
      return
    }
    try {
      if (!chartLib.current) {
        chartLib.current = await import('lightweight-charts')
      }
      const { createChart, CandlestickSeries, createSeriesMarkers, ColorType } = chartLib.current

      destroyChart()
      chartApi.current = createChart(chartRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: '#1a1a2e' },
          textColor: '#d1d4dc',
        },
        grid: {
          vertLines: { color: '#2B2B43' },
          horzLines: { color: '#2B2B43' },
        },
        width: Math.max(chartRef.current.clientWidth, 100),
        height: 480,
        timeScale: { timeVisible: true, secondsVisible: false },
      })

      const priceFormat = inferPriceFormat(review.candles)
      const series = chartApi.current.addSeries(CandlestickSeries, {
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderVisible: false,
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
        priceFormat,
      })

      const candleSecs = review.candles
        .map((c) => Math.floor(c.time / 1000))
        .sort((a, b) => a - b)

      series.setData(
        review.candles.map((c) => ({
          time: Math.floor(c.time / 1000) as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })),
      )

      const candleStart = review.candles[0]?.time ?? 0
      const candleEnd = review.candles[review.candles.length - 1]?.time ?? 0

      const lwMarkers = review.markers
        .filter((m) => m.time >= candleStart && m.time <= candleEnd)
        .map((m) => ({
          time: snapToNearestCandleSec(m.time, candleSecs),
          position: m.marker_type === 'entry'
            ? (m.side === 'long' ? 'belowBar' as const : 'aboveBar' as const)
            : (m.side === 'long' ? 'aboveBar' as const : 'belowBar' as const),
          color: m.marker_type === 'entry'
            ? '#2196F3'
            : (m.pnl >= 0 ? '#26a69a' : '#ef5350'),
          shape: m.marker_type === 'entry'
            ? (m.side === 'long' ? 'arrowUp' as const : 'arrowDown' as const)
            : 'circle' as const,
          text: m.label,
        }))

      if (fitToMarkers && lwMarkers.length >= 2) {
        const times = lwMarkers.map((m) => m.time as number).sort((a, b) => a - b)
        chartApi.current.timeScale().setVisibleRange({
          from: times[0] as UTCTimestamp,
          to: times[times.length - 1] as UTCTimestamp,
        })
      } else {
        chartApi.current.timeScale().fitContent()
      }

      try {
        markersApi.current = createSeriesMarkers(series, lwMarkers)
      } catch (markerErr) {
        console.warn('标记渲染失败，K线仍可用', markerErr)
      }
    } catch (e) {
      console.error('K线渲染失败', e)
      message.error('K 线图表渲染失败，请刷新重试')
    }
  }, [destroyChart])

  const loadTable = useCallback(async () => {
    setTableLoading(true)
    try {
      const rows = await apiClient.queryPositionsHistory({
        all: true,
        symbol: tableSymbol,
        startTime: tableTimeRange?.[0]?.startOf('day').toISOString(),
        endTime: tableTimeRange?.[1]?.endOf('day').toISOString(),
        sortBy: tableSortBy,
        order: tableOrder,
      })
      setTablePositions(rows)
    } catch {
      setTablePositions([])
    } finally {
      setTableLoading(false)
    }
  }, [tableSymbol, tableTimeRange, tableSortBy, tableOrder])

  const loadChart = useCallback(async () => {
    const id = ++loadId.current
    setLoading(true)
    try {
      const selectedRows = markerMode === 'selected'
        ? tablePositions.filter((p) => selectedIds.includes(positionRowKey(p)))
        : []
      const review = await apiClient.getChartReview(symbol, timeframe, {
        markerMode,
        positionIds: markerMode === 'selected'
          ? [...new Set(selectedRows.map((p) => p.position_id))]
          : undefined,
        closeTimes: markerMode === 'selected'
          ? selectedRows.map((p) => p.close_time)
          : undefined,
        startTime: markerMode === 'time_range' ? chartTimeRange?.[0]?.startOf('day').toISOString() : undefined,
        endTime: markerMode === 'time_range' ? chartTimeRange?.[1]?.endOf('day').toISOString() : undefined,
      })
      if (id !== loadId.current) return
      setData(review)
      setLoading(false)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          void renderChart(review, markerMode !== 'all' && markerMode !== 'none')
        })
      })
    } catch (err: unknown) {
      if (id !== loadId.current) return
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(msg || '加载复盘数据失败')
      setData(null)
      setLoading(false)
    }
  }, [symbol, timeframe, markerMode, selectedIds, chartTimeRange, tablePositions, renderChart])

  useEffect(() => {
    if (!ready) return
    loadTable()
  }, [ready, loadTable])

  useEffect(() => {
    if (!ready) return
    loadChart()
    return () => { destroyChart() }
  }, [ready, loadChart, destroyChart])

  useEffect(() => {
    const onResize = () => {
      if (chartRef.current && chartApi.current) {
        chartApi.current.applyOptions({ width: chartRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const currentSym = symbols.find((s) => s.symbol === symbol)
  const intervals = useMemo(() => {
    const list = currentSym?.intervals || ['15m', '1h', '4h', '1d']
    return [...list].sort(
      (a, b) => (INTERVAL_ORDER.indexOf(a) === -1 ? 99 : INTERVAL_ORDER.indexOf(a))
        - (INTERVAL_ORDER.indexOf(b) === -1 ? 99 : INTERVAL_ORDER.indexOf(b)),
    )
  }, [currentSym])

  const chartStats = useMemo(() => {
    const positions = data?.positions ?? []
    const winCount = positions.filter((p) => p.pnl >= 0).length
    return { count: positions.length, winCount, lossCount: positions.length - winCount }
  }, [data])

  const handleChartSymbolChange = (v: string) => {
    setSymbol(v)
    const sym = symbols.find((s) => s.symbol === v)
    if (sym) setTimeframe((prev) => pickInterval(prev, sym.intervals))
    setSelectedIds([])
  }

  const jumpToChartSymbol = (inst: string) => {
    setSymbol(inst)
    const sym = symbols.find((s) => s.symbol === inst)
    if (sym) setTimeframe((prev) => pickInterval(prev, sym.intervals))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const rowSelection: TableProps<PositionHistory>['rowSelection'] = {
    selectedRowKeys: selectedIds,
    onChange: (keys) => setSelectedIds(keys as string[]),
    preserveSelectedRowKeys: true,
  }

  return (
    <div>
      <Card
        title={<span><LineChartOutlined /> 持仓复盘 · K 线标注</span>}
        extra={
          <Space wrap>
            <Select
              style={{ width: 180 }}
              value={symbol}
              onChange={handleChartSymbolChange}
              options={symbols.map((s) => ({
                value: s.symbol,
                label: `${s.base} (${s.source})`,
              }))}
            />
            <Select
              style={{ width: 100 }}
              value={timeframe}
              onChange={setTimeframe}
              options={intervals.map((iv) => ({ value: iv, label: iv }))}
            />
            <Button icon={<ReloadOutlined />} onClick={() => { loadChart(); loadTable() }} loading={loading}>
              刷新
            </Button>
          </Space>
        }
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="默认展示全部进出场标注。可切换为「时间范围 / 选中订单 / 不展示」后点「应用图表」。切换周期会自动对齐 K 线边界。"
        />

        <Space direction="vertical" style={{ width: '100%', marginBottom: 12 }} size="middle">
          <Space wrap>
            <span>图表标注：</span>
            <Segmented
              value={markerMode}
              onChange={(v) => setMarkerMode(v as ChartMarkerMode)}
              options={[
                { label: '不展示', value: 'none' },
                { label: '全部', value: 'all' },
                { label: '时间范围', value: 'time_range' },
                { label: '选中订单', value: 'selected' },
              ]}
            />
            {markerMode === 'time_range' && (
              <RangePicker
                value={chartTimeRange}
                onChange={(v) => setChartTimeRange(v as [Dayjs, Dayjs] | null)}
              />
            )}
            {markerMode === 'selected' && (
              <Tag color="blue">已选 {selectedIds.length} 笔（在下方表格勾选）</Tag>
            )}
            <Button type="primary" onClick={loadChart} loading={loading}>
              应用图表
            </Button>
          </Space>
        </Space>

        {data && (
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Statistic title="图表内笔数" value={chartStats.count} />
            </Col>
            <Col span={6}>
              <Statistic
                title="图表合计盈亏"
                value={data.total_pnl}
                precision={2}
                suffix="USDT"
                valueStyle={{ color: data.total_pnl >= 0 ? '#3f8600' : '#cf1322' }}
              />
            </Col>
            <Col span={6}>
              <Statistic title="盈利 / 亏损" value={`${chartStats.winCount} / ${chartStats.lossCount}`} />
            </Col>
            <Col span={6}>
              <Statistic title={`数据源 · ${data.interval}`} value={data.data_source} />
            </Col>
          </Row>
        )}
        <Spin spinning={loading} tip="加载 K 线与标注中...">
          <div ref={chartRef} style={{ width: '100%', minHeight: 480 }} />
        </Spin>
      </Card>

      <Card title="历史持仓明细" style={{ marginTop: 16 }}>
        <Space wrap style={{ marginBottom: 12 }}>
          <Select
            allowClear
            placeholder="全部币种"
            style={{ width: 200 }}
            value={tableSymbol}
            onChange={(v) => setTableSymbol(v)}
            options={symbols.map((s) => ({
              value: s.symbol,
              label: s.symbol.replace('-USDT-SWAP', ''),
            }))}
          />
          <RangePicker
            placeholder={['平仓开始', '平仓结束']}
            value={tableTimeRange}
            onChange={(v) => setTableTimeRange(v as [Dayjs, Dayjs] | null)}
          />
          <Radio.Group
            value={tableSortBy}
            onChange={(e) => setTableSortBy(e.target.value)}
            optionType="button"
            options={[
              { label: '按时间', value: 'close_time' },
              { label: '按盈亏', value: 'pnl' },
            ]}
          />
          <Radio.Group
            value={tableOrder}
            onChange={(e) => setTableOrder(e.target.value)}
            optionType="button"
            options={[
              { label: '降序', value: 'desc' },
              { label: '升序', value: 'asc' },
            ]}
          />
          <Button onClick={loadTable} loading={tableLoading}>刷新</Button>
          <Tag color="default">
            {tableSymbol ? `已筛选 ${tablePositions.length} 笔` : `全部 ${tablePositions.length} 笔`}
          </Tag>
        </Space>
        <Table
          dataSource={tablePositions}
          rowKey={positionRowKey}
          size="small"
          loading={tableLoading}
          rowSelection={markerMode === 'selected' ? rowSelection : undefined}
          pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 笔` }}
          onRow={(record) => ({
            onClick: () => {
              if (markerMode !== 'selected') return
              const key = positionRowKey(record)
              setSelectedIds((prev) =>
                prev.includes(key)
                  ? prev.filter((id) => id !== key)
                  : [...prev, key],
              )
            },
            style: { cursor: markerMode === 'selected' ? 'pointer' : 'default' },
          })}
          columns={[
            {
              title: '币种', dataIndex: 'symbol', width: 110,
              render: (s: string) => (
                <Button type="link" size="small" style={{ padding: 0 }}
                  onClick={(e) => { e.stopPropagation(); jumpToChartSymbol(s) }}>
                  {s.replace('-USDT-SWAP', '')}
                </Button>
              ),
            },
            {
              title: '平仓时间', dataIndex: 'close_time', width: 170,
              sorter: (a, b) => new Date(a.close_time).getTime() - new Date(b.close_time).getTime(),
              render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-',
            },
            {
              title: '方向', dataIndex: 'side', width: 70,
              filters: [{ text: '多', value: 'long' }, { text: '空', value: 'short' }],
              onFilter: (v, r) => r.side === v,
              render: (s: string) => <Tag color={s === 'long' ? 'green' : 'red'}>{s === 'long' ? '多' : '空'}</Tag>,
            },
            { title: '杠杆', dataIndex: 'leverage', width: 70, render: (v: number) => `${v}x` },
            { title: '开仓价', dataIndex: 'open_avg_price', render: (v: number) => v?.toFixed(4) },
            { title: '平仓价', dataIndex: 'close_avg_price', render: (v: number) => v?.toFixed(4) },
            {
              title: '盈亏', dataIndex: 'pnl', width: 100,
              sorter: (a, b) => a.pnl - b.pnl,
              render: (v: number) => (
                <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322', fontWeight: 600 }}>
                  {v >= 0 ? '+' : ''}{v?.toFixed(4)}
                </span>
              ),
            },
            {
              title: '类型', dataIndex: 'close_type', width: 100,
              render: (t: string) => (
                <Tag color={t === 'liquidation' ? 'red' : 'blue'}>
                  {CLOSE_TYPE_LABELS[t] || t}
                </Tag>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
