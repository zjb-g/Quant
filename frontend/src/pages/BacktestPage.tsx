import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Card, Select, Table, Tag, Statistic, Row, Col, Spin, message, Button, Input, Space, Alert, Progress,
} from 'antd'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import {
  apiClient,
  type BacktestSummary,
  type BacktestTrade,
  type BacktestJob,
  type StrategyInfo,
} from '../api/client'
import { useIsMobile } from '../hooks/useIsMobile'

export default function BacktestPage() {
  const [backtestIds, setBacktestIds] = useState<{id: string; strategy: string; timestamp: string}[]>([])
  const [selectedId, setSelectedId] = useState<string | undefined>()
  const [summary, setSummary] = useState<BacktestSummary | null>(null)
  const [trades, setTrades] = useState<BacktestTrade[]>([])
  const [loading, setLoading] = useState(false)
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [runStrategy, setRunStrategy] = useState('EmaCrossoverStrategy')
  const [timerange, setTimerange] = useState('')
  const [runningJob, setRunningJob] = useState<BacktestJob | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isMobile = useIsMobile()

  const refreshList = useCallback((autoSelectLatest = false) => {
    return apiClient.getBacktestList().then((list) => {
      setBacktestIds(list)
      if (autoSelectLatest && list.length > 0) {
        setSelectedId(list[0].id)
      }
      return list
    }).catch(() => {
      message.error('无法加载回测列表')
      return []
    })
  }, [])

  useEffect(() => {
    refreshList(true)
    apiClient.getStrategies().then((list) => {
      setStrategies(list)
      const preferred = list.find((s) => s.name === 'EmaCrossoverStrategy') ?? list[0]
      if (preferred) setRunStrategy(preferred.name)
    }).catch(() => {})
    apiClient.getBacktestDefaultTimerange()
      .then((r) => setTimerange(r.timerange))
      .catch(() => setTimerange('20250601-20250630'))
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [refreshList])

  useEffect(() => {
    if (!selectedId) {
      setSummary(null)
      setTrades([])
      return
    }
    setLoading(true)
    setLastError(null)
    apiClient
      .getBacktestResult(selectedId)
      .then((r) => {
        setSummary(r.summary)
        setTrades(r.trades)
      })
      .catch((err: unknown) => {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        const text = msg || '加载回测结果失败'
        setLastError(text)
        message.error(text)
        setSummary(null)
        setTrades([])
      })
      .finally(() => setLoading(false))
  }, [selectedId])

  const handleJobUpdate = useCallback((job: BacktestJob) => {
    setRunningJob(job)
    if (job.status === 'done') {
      if (pollRef.current) clearInterval(pollRef.current)
      setLastError(null)
      message.success('回测完成')
      void refreshList(true).then(() => {
        if (job.result_id) setSelectedId(job.result_id)
      })
      setRunningJob(null)
    } else if (job.status === 'error') {
      if (pollRef.current) clearInterval(pollRef.current)
      const errText = job.error || '回测失败'
      setLastError(errText)
      message.error(errText, 8)
      setRunningJob(null)
    }
  }, [refreshList])

  const pollJob = (jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current)

    const tick = async () => {
      try {
        const job = await apiClient.getBacktestJob(jobId)
        handleJobUpdate(job)
      } catch (err: unknown) {
        if (pollRef.current) clearInterval(pollRef.current)
        const status = (err as { response?: { status?: number } })?.response?.status
        const msg = status === 404
          ? '回测任务已丢失（可能服务重启了），请刷新列表查看历史结果'
          : '查询回测进度失败，请稍后刷新列表'
        setLastError(msg)
        message.warning(msg)
        setRunningJob(null)
      }
    }

    void tick()
    pollRef.current = setInterval(tick, 2000)
  }

  const handleRunBacktest = async () => {
    if (!timerange.match(/^\d{8}-\d{8}$/)) {
      message.warning('时间范围格式应为 YYYYMMDD-YYYYMMDD')
      return
    }
    const [startStr, endStr] = timerange.split('-')
    const parseYmd = (s: string) => {
      const y = Number(s.slice(0, 4))
      const m = Number(s.slice(4, 6))
      const d = Number(s.slice(6, 8))
      const dt = new Date(y, m - 1, d)
      if (dt.getFullYear() !== y || dt.getMonth() !== m - 1 || dt.getDate() !== d) return null
      return dt
    }
    const startDate = parseYmd(startStr)
    const endDate = parseYmd(endStr)
    if (!startDate || !endDate || startStr.slice(0, 4) < '2000' || endStr.slice(0, 4) < '2000') {
      message.warning('日期无效，请使用 YYYYMMDD-YYYYMMDD（年份不早于 2000，例如 20200401-20260625）')
      return
    }
    if (startDate > endDate) {
      message.warning('开始日期不能晚于结束日期')
      return
    }
    setLastError(null)
    setSummary(null)
    setTrades([])
    try {
      const job = await apiClient.runBacktest(runStrategy, timerange, true)
      setRunningJob(job)
      if (job.status === 'done') {
        handleJobUpdate(job)
        return
      }
      if (job.status === 'error') {
        handleJobUpdate(job)
        return
      }
      message.info('回测已启动，请稍候…')
      pollJob(job.id)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const text = msg || '启动回测失败'
      setLastError(text)
      message.error(text, 8)
    }
  }

  const equityData = trades.length > 0
    ? trades.reduce<{ timestamp: string; cumProfit: number }[]>((acc, t) => {
        const prev = acc.length > 0 ? acc[acc.length - 1].cumProfit : 0
        acc.push({ timestamp: t.close_date, cumProfit: prev + t.profit_abs })
        return acc
      }, [])
    : []

  return (
    <div>
      <Card title="运行回测（历史 K 线）" style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="使用本地 Binance 永续 K 线数据。建议先用 1–3 个月短区间测试；默认已改为最近 90 天。"
        />
        {lastError && (
          <Alert
            type="error"
            showIcon
            closable
            style={{ marginBottom: 12 }}
            message="回测错误"
            description={<pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>{lastError}</pre>}
            onClose={() => setLastError(null)}
          />
        )}
        <Space direction={isMobile ? 'vertical' : 'horizontal'} wrap style={{ width: '100%' }}>
          <Select
            className={isMobile ? 'mobile-full-width' : undefined}
            style={{ width: isMobile ? '100%' : 240 }}
            value={runStrategy}
            onChange={setRunStrategy}
            options={strategies.map((s) => ({
              value: s.name,
              label: s.id && s.id !== s.name ? `${s.name} (${s.id})` : s.name,
              disabled: s.has_errors,
            }))}
          />
          <Input
            className={isMobile ? 'mobile-full-width' : undefined}
            style={{ width: isMobile ? '100%' : 220 }}
            value={timerange}
            onChange={(e) => setTimerange(e.target.value)}
            placeholder="20250601-20250630"
            addonBefore="时间范围"
          />
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleRunBacktest}
            disabled={!!runningJob}
          >
            运行回测
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => refreshList(false)}>刷新列表</Button>
        </Space>
        {runningJob && (
          <div style={{ marginTop: 16 }}>
            <Progress percent={runningJob.status === 'running' ? 50 : 10} status="active" />
            <span style={{ marginLeft: 8, color: '#999' }}>
              {runningJob.strategy} · {runningJob.timerange} · {runningJob.status}
            </span>
          </div>
        )}
      </Card>

      <Card title="回测结果选择" style={{ marginBottom: 16 }}>
        <Select
          style={{ width: '100%', maxWidth: 480 }}
          placeholder="选择回测结果"
          value={selectedId}
          onChange={setSelectedId}
          options={backtestIds.map((bt) => ({
            label: `${bt.strategy} (${bt.timestamp})`,
            value: bt.id,
          }))}
        />
        {!loading && !summary && selectedId && !lastError && (
          <Alert style={{ marginTop: 12 }} type="info" message="正在加载或该结果无数据，请稍候或换一个结果" />
        )}
        {!selectedId && backtestIds.length > 0 && (
          <Alert style={{ marginTop: 12 }} type="info" message="请从上方下拉框选择一个历史回测结果" />
        )}
        {backtestIds.length === 0 && !runningJob && (
          <Alert style={{ marginTop: 12 }} type="warning" message="暂无回测结果，请先运行回测" />
        )}
      </Card>

      {loading && <Spin size="large" style={{ display: 'flex', justifyContent: 'center', padding: 60 }} />}

      {summary && !loading && (
        <>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={12} sm={8} md={4}><Card><Statistic title="总交易数" value={summary.total_trades} /></Card></Col>
            <Col xs={12} sm={8} md={4}>
              <Card>
                <Statistic
                  title="总收益"
                  value={summary.total_profit_pct}
                  precision={2}
                  suffix="%"
                  valueStyle={{ color: summary.total_profit_pct >= 0 ? '#3f8600' : '#cf1322' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Card>
                <Statistic
                  title="最大回撤"
                  value={summary.max_drawdown_pct}
                  precision={2}
                  suffix="%"
                  valueStyle={{ color: '#cf1322' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={4}><Card><Statistic title="胜率" value={summary.win_rate} precision={1} suffix="%" /></Card></Col>
            <Col xs={12} sm={8} md={4}><Card><Statistic title="Sharpe" value={summary.sharpe} precision={2} /></Card></Col>
            <Col xs={24} sm={12} md={4}><Card><Statistic title="时间范围" value={summary.timerange} valueStyle={{ fontSize: 14 }} /></Card></Col>
          </Row>

          {equityData.length > 0 && (
            <Card title="累计收益曲线" style={{ marginBottom: 16 }}>
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={equityData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="timestamp" fontSize={11} />
                  <YAxis fontSize={11} />
                  <Tooltip />
                  <Line type="monotone" dataKey="cumProfit" stroke="#1890ff" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}

          {trades.length > 0 && (
            <Card title={`交易明细（${trades.length} 笔）`}>
              <Table
                dataSource={trades.slice(0, 200)}
                rowKey={(r) => `${r.pair}-${r.open_date}-${r.close_date}`}
                size="small"
                pagination={{ pageSize: 50 }}
                scroll={{ x: 800 }}
                columns={[
                  { title: '币种', dataIndex: 'pair', key: 'pair' },
                  {
                    title: '方向',
                    dataIndex: 'side',
                    key: 'side',
                    render: (s: string) => (
                      <Tag color={s === 'long' ? 'green' : 'red'}>{s === 'long' ? '多' : '空'}</Tag>
                    ),
                  },
                  { title: '开仓时间', dataIndex: 'open_date', key: 'open_date', width: 160 },
                  { title: '平仓时间', dataIndex: 'close_date', key: 'close_date', width: 160 },
                  { title: '开仓价', dataIndex: 'open_rate', key: 'open_rate' },
                  { title: '平仓价', dataIndex: 'close_rate', key: 'close_rate' },
                  {
                    title: '收益率',
                    dataIndex: 'profit_pct',
                    key: 'profit_pct',
                    render: (v: number) => (
                      <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>
                        {v >= 0 ? '+' : ''}{v?.toFixed(2)}%
                      </span>
                    ),
                  },
                  { title: '退出原因', dataIndex: 'exit_reason', key: 'exit_reason' },
                ]}
              />
            </Card>
          )}
        </>
      )}
    </div>
  )
}
