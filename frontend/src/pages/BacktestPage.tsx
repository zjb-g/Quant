import { useState, useEffect, useRef } from 'react'
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
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refreshList = () => {
    apiClient.getBacktestList().then(setBacktestIds).catch(() => message.error('无法加载回测列表'))
  }

  useEffect(() => {
    refreshList()
    apiClient.getStrategies().then((list) => {
      setStrategies(list)
      if (list.length) setRunStrategy(list[0].name)
    }).catch(() => {})
    apiClient.getBacktestDefaultTimerange()
      .then((r) => setTimerange(r.timerange))
      .catch(() => setTimerange('20250601-20260601'))
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoading(true)
    apiClient
      .getBacktestResult(selectedId)
      .then((r) => {
        setSummary(r.summary)
        setTrades(r.trades)
      })
      .catch(() => message.error('加载回测结果失败'))
      .finally(() => setLoading(false))
  }, [selectedId])

  const pollJob = (jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const job = await apiClient.getBacktestJob(jobId)
        setRunningJob(job)
        if (job.status === 'done') {
          if (pollRef.current) clearInterval(pollRef.current)
          message.success('回测完成')
          refreshList()
          if (job.result_id) setSelectedId(job.result_id)
          setRunningJob(null)
        } else if (job.status === 'error') {
          if (pollRef.current) clearInterval(pollRef.current)
          message.error(job.error || '回测失败')
          setRunningJob(null)
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current)
        setRunningJob(null)
      }
    }, 2000)
  }

  const handleRunBacktest = async () => {
    if (!timerange.match(/^\d{8}-\d{8}$/)) {
      message.warning('时间范围格式应为 YYYYMMDD-YYYYMMDD')
      return
    }
    try {
      const job = await apiClient.runBacktest(runStrategy, timerange, true)
      setRunningJob(job)
      message.info('回测已启动，请稍候…')
      pollJob(job.id)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(msg || '启动回测失败')
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
          message="使用本地 Binance 永续 K 线数据，通过 Freqtrade 引擎回测。首次运行约需 30–120 秒。"
        />
        <Space wrap>
          <Select
            style={{ width: 240 }}
            value={runStrategy}
            onChange={setRunStrategy}
            options={strategies.map((s) => ({
              value: s.name,
              label: s.id && s.id !== s.name ? `${s.name} (${s.id})` : s.name,
              disabled: s.has_errors,
            }))}
          />
          <Input
            style={{ width: 220 }}
            value={timerange}
            onChange={(e) => setTimerange(e.target.value)}
            placeholder="20250601-20260601"
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
          <Button icon={<ReloadOutlined />} onClick={refreshList}>刷新列表</Button>
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
          style={{ width: 400 }}
          placeholder="选择回测结果"
          value={selectedId}
          onChange={setSelectedId}
          options={backtestIds.map((bt) => ({ label: `${bt.strategy} (${bt.timestamp})`, value: bt.id }))}
        />
      </Card>

      {loading && <Spin size="large" style={{ display: 'flex', justifyContent: 'center', padding: 60 }} />}

      {summary && !loading && (
        <>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col span={4}><Card><Statistic title="总交易数" value={summary.total_trades} /></Card></Col>
            <Col span={4}>
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
            <Col span={4}>
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
            <Col span={4}><Card><Statistic title="胜率" value={summary.win_rate} precision={1} suffix="%" /></Card></Col>
            <Col span={4}><Card><Statistic title="Sharpe" value={summary.sharpe} precision={2} /></Card></Col>
            <Col span={4}><Card><Statistic title="时间范围" value={summary.timerange} valueStyle={{ fontSize: 14 }} /></Card></Col>
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
