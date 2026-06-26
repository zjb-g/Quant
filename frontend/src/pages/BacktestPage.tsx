import { useState, useEffect } from 'react'
import { Card, Select, Table, Tag, Statistic, Row, Col, Spin, message } from 'antd'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from 'recharts'
import { apiClient, type BacktestSummary, type BacktestTrade } from '../api/client'

export default function BacktestPage() {
  const [backtestIds, setBacktestIds] = useState<string[]>([])
  const [selectedId, setSelectedId] = useState<string | undefined>()
  const [summary, setSummary] = useState<BacktestSummary | null>(null)
  const [trades, setTrades] = useState<BacktestTrade[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    apiClient.getBacktestList().then(setBacktestIds).catch(() => {
      message.warning('后端未连接，显示占位')
      setBacktestIds(['mock-2026-06-26'])
    })
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
      .catch(() => {
        // mock 占位
        setSummary({
          strategy: 'EmaCrossoverStrategy',
          timerange: '2025-06-01 ~ 2026-06-25',
          total_trades: 1722,
          total_profit_pct: -26.49,
          max_drawdown_pct: 26.91,
          win_rate: 58.4,
          avg_duration: '1:31:00',
          sharpe: -9.65,
          sortino: -16.28,
        })
        setTrades([])
      })
      .finally(() => setLoading(false))
  }, [selectedId])

  // 权益曲线（从 trades 累计）
  const equityData = trades.length > 0
    ? trades.reduce<{ timestamp: string; cumProfit: number }[]>((acc, t) => {
        const prev = acc.length > 0 ? acc[acc.length - 1].cumProfit : 0
        acc.push({ timestamp: t.close_date, cumProfit: prev + t.profit_abs })
        return acc
      }, [])
    : []

  return (
    <div>
      <Card title="回测结果选择" style={{ marginBottom: 16 }}>
        <Select
          style={{ width: 400 }}
          placeholder="选择回测结果"
          value={selectedId}
          onChange={setSelectedId}
          options={backtestIds.map((id) => ({ label: id, value: id }))}
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
            <Col span={4}><Card><Statistic title="Sortino" value={summary.sortino} precision={2} /></Card></Col>
          </Row>

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

          {trades.length > 0 && (
            <Card title={`交易明细（${trades.length} 笔）`}>
              <Table
                dataSource={trades.slice(0, 200)}
                rowKey={(r) => `${r.pair}-${r.open_date}`}
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
                    sorter: (a: BacktestTrade, b: BacktestTrade) => a.profit_pct - b.profit_pct,
                    render: (v: number) => (
                      <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>
                        {v >= 0 ? '+' : ''}{v.toFixed(2)}%
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
