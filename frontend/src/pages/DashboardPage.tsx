import { useState, useEffect } from 'react'
import { Row, Col, Card, Statistic, Table, Tag, Spin, message } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  StopOutlined,
  SafetyOutlined,
} from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { apiClient, type SystemStatus, type Position, type EquityPoint, type RiskState } from '../api/client'

export default function DashboardPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [equity, setEquity] = useState<EquityPoint[]>([])
  const [risk, setRisk] = useState<RiskState | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      const [s, p, e, r] = await Promise.allSettled([
        apiClient.getSystemStatus(),
        apiClient.getPositions(),
        apiClient.getEquityCurve(30),
        apiClient.getRiskState(),
      ])
      if (s.status === 'fulfilled') setStatus(s.value)
      if (p.status === 'fulfilled') setPositions(p.value)
      if (e.status === 'fulfilled') setEquity(e.value)
      if (r.status === 'fulfilled') setRisk(r.value)
      if (s.status === 'rejected') {
        message.warning('后端未连接')
      }
      setLoading(false)
    }
    load()
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [])

  if (loading) {
    return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', padding: 100 }} />
  }

  const totalPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0)

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic
              title="Bot 状态"
              value={status?.bot_running ? '运行中' : '已停止'}
              valueStyle={{ color: status?.bot_running ? '#3f8600' : '#cf1322' }}
              prefix={status?.bot_running ? <ArrowUpOutlined /> : <StopOutlined />}
            />
            <Tag color={status?.dry_run ? 'blue' : 'red'} style={{ marginTop: 8 }}>
              {status?.dry_run ? 'DRY-RUN' : 'LIVE'}
            </Tag>
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic
              title="未实现盈亏"
              value={totalPnl}
              precision={2}
              suffix="USDT"
              valueStyle={{ color: totalPnl >= 0 ? '#3f8600' : '#cf1322' }}
              prefix={totalPnl >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic
              title="总敞口"
              value={risk?.current_total_notional ?? 0}
              precision={2}
              suffix="USDT"
              prefix={<SafetyOutlined />}
            />
            <span style={{ fontSize: 12, color: '#999' }}>
              上限 {risk?.max_total_notional ?? '-'} USDT
            </span>
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic
              title="最大回撤"
              value={risk?.max_drawdown_pct ?? 0}
              precision={2}
              suffix="%"
              valueStyle={{ color: (risk?.max_drawdown_pct ?? 0) > 10 ? '#cf1322' : '#3f8600' }}
            />
            <span style={{ fontSize: 12, color: '#999' }}>
              限额 {risk?.max_drawdown_pct ?? '-'}%
            </span>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <Card title="权益曲线（30 天）" extra={<Tag color={risk?.kill_switch ? 'red' : 'green'}>{risk?.kill_switch ? 'KILL SWITCH ON' : '风控正常'}</Tag>}>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={equity}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="timestamp" fontSize={11} />
                <YAxis fontSize={11} />
                <Tooltip />
                <Line type="monotone" dataKey="equity" stroke="#1890ff" strokeWidth={2} dot={false} />
                <ReferenceLine y={risk?.equity_high_watermark} stroke="#888" strokeDasharray="5 5" label="高水位" />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="风控状态">
            <Statistic
              title="每日亏损"
              value={risk?.daily_loss_pct ?? 0}
              precision={2}
              suffix="%"
              valueStyle={{ color: (risk?.daily_loss_pct ?? 0) > (risk?.daily_loss_limit_pct ?? 5) ? '#cf1322' : '#3f8600' }}
            />
            <Statistic
              title="Kill Switch"
              value={risk?.kill_switch ? '已激活' : '未激活'}
              valueStyle={{ color: risk?.kill_switch ? '#cf1322' : '#3f8600' }}
              style={{ marginTop: 16 }}
            />
            {risk?.kill_switch_reason && (
              <div style={{ marginTop: 8, fontSize: 12, color: '#cf1322' }}>
                原因：{risk.kill_switch_reason}
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Card
        title={status?.bot_running && status?.dry_run ? '模拟持仓（dry-run）' : '当前持仓'}
        extra={status?.bot_running && status?.dry_run ? <Tag color="blue">DRY-RUN</Tag> : undefined}
        style={{ marginTop: 16 }}
      >
        <Table
          dataSource={positions}
          rowKey={(r) => `${r.symbol}-${r.side}`}
          pagination={false}
          size="small"
          scroll={{ x: 640 }}
          locale={{ emptyText: status?.bot_running ? '暂无持仓，等待策略开仓…' : 'Bot 未运行或无持仓' }}
          columns={[
            { title: '币种', dataIndex: 'symbol', key: 'symbol' },
            {
              title: '方向',
              dataIndex: 'side',
              key: 'side',
              render: (s: string) => (
                <Tag color={s === 'long' ? 'green' : 'red'}>
                  {s === 'long' ? '多' : '空'}
                </Tag>
              ),
            },
            { title: '数量', dataIndex: 'contracts', key: 'contracts', precision: 4 },
            { title: '开仓价', dataIndex: 'entry_price', key: 'entry_price', precision: 2 },
            { title: '标记价', dataIndex: 'mark_price', key: 'mark_price', precision: 2 },
            { title: '杠杆', dataIndex: 'leverage', key: 'leverage', suffix: 'x' },
            {
              title: '未实现盈亏',
              dataIndex: 'unrealized_pnl',
              key: 'unrealized_pnl',
              precision: 2,
              suffix: 'USDT',
              render: (v: number) => (
                <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>
                  {v >= 0 ? '+' : ''}{v.toFixed(2)}
                </span>
              ),
            },
            { title: '强平价', dataIndex: 'liquidation_price', key: 'liquidation_price' },
          ]}
        />
      </Card>
    </div>
  )
}
