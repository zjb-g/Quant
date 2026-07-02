import { useState, useEffect } from 'react'
import { Row, Col, Card, Statistic, Table, Tag, message } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  StopOutlined,
  SafetyOutlined,
  WalletOutlined,
  DollarOutlined,
  FundOutlined,
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
import LoadingState from '../components/LoadingState'
import EmptyState from '../components/EmptyState'
import { pnlColor, numAlign } from '../theme'
import { useIsMobile } from '../hooks/useIsMobile'

export default function DashboardPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [equity, setEquity] = useState<EquityPoint[]>([])
  const [risk, setRisk] = useState<RiskState | null>(null)
  const [loading, setLoading] = useState(true)
  const isMobile = useIsMobile()

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
    return <LoadingState fullPage tip="正在加载仪表盘数据..." />
  }

  const totalPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0)
  const positionCount = positions.length

  // 计算资产总额估算（简单处理）
  const estimatedTotal = risk?.equity_high_watermark
    ? risk.equity_high_watermark + totalPnl
    : undefined

  return (
    <div>
      {/* 核心指标卡片 — 首屏可见 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={8} lg={6}>
          <Card hoverable>
            <Statistic
              title="总资产预估"
              value={estimatedTotal ?? 0}
              precision={2}
              suffix="USDT"
              prefix={<WalletOutlined />}
              valueStyle={{ fontSize: isMobile ? 22 : 28 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={6}>
          <Card hoverable>
            <Statistic
              title="今日盈亏"
              value={totalPnl}
              precision={2}
              suffix="USDT"
              valueStyle={{
                color: pnlColor(totalPnl),
                fontSize: isMobile ? 22 : 28,
              }}
              prefix={totalPnl >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={6}>
          <Card hoverable>
            <Statistic
              title="当前持仓"
              value={positionCount}
              suffix="个"
              prefix={<FundOutlined />}
              valueStyle={{ fontSize: isMobile ? 22 : 28 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={6}>
          <Card hoverable>
            <Statistic
              title="Bot 状态"
              value={status?.bot_running ? '运行中' : '已停止'}
              valueStyle={{
                color: status?.bot_running ? '#52c41a' : '#ff4d4f',
                fontSize: isMobile ? 22 : 28,
              }}
              prefix={status?.bot_running ? <ArrowUpOutlined /> : <StopOutlined />}
            />
            <div style={{ marginTop: 8 }}>
              <Tag color={status?.dry_run ? 'blue' : status?.bot_running ? 'red' : 'default'}>
                {status?.dry_run ? 'DRY-RUN' : status?.bot_running ? 'LIVE' : 'STOPPED'}
              </Tag>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 次行：敞口 & 回撤 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} sm={8} md={6}>
          <Card>
            <Statistic
              title="总敞口"
              value={risk?.current_total_notional ?? 0}
              precision={2}
              suffix="USDT"
              prefix={<SafetyOutlined />}
            />
            <div style={{ marginTop: 4, fontSize: 12, color: 'var(--app-text-muted)' }}>
              上限 {risk?.max_total_notional ?? '-'} USDT
            </div>
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Card>
            <Statistic
              title="最大回撤"
              value={risk?.max_drawdown_pct ?? 0}
              precision={2}
              suffix="%"
              valueStyle={{ color: (risk?.max_drawdown_pct ?? 0) > 10 ? '#ff4d4f' : '#52c41a' }}
            />
            <div style={{ marginTop: 4, fontSize: 12, color: 'var(--app-text-muted)' }}>
              限额 {risk?.max_drawdown_pct ?? '-'}%
            </div>
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Card>
            <Statistic
              title="每日亏损"
              value={risk?.daily_loss_pct ?? 0}
              precision={2}
              suffix="%"
              valueStyle={{
                color: (risk?.daily_loss_pct ?? 0) > (risk?.daily_loss_limit_pct ?? 5)
                  ? '#ff4d4f' : '#52c41a',
              }}
            />
            <div style={{ marginTop: 4, fontSize: 12, color: 'var(--app-text-muted)' }}>
              限额 {risk?.daily_loss_limit_pct ?? '-'}%
            </div>
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Card>
            <Statistic
              title="Kill Switch"
              value={risk?.kill_switch ? '已激活' : '未激活'}
              valueStyle={{ color: risk?.kill_switch ? '#ff4d4f' : '#52c41a' }}
            />
            {risk?.kill_switch_reason && (
              <div style={{ marginTop: 4, fontSize: 12, color: '#ff4d4f' }}>
                {risk.kill_switch_reason}
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* 权益曲线 + 风控卡片 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <Card
            title="权益曲线（30 天）"
            extra={
              <Tag color={risk?.kill_switch ? 'red' : 'green'}>
                {risk?.kill_switch ? 'KILL SWITCH ON' : '风控正常'}
              </Tag>
            }
          >
            {equity.length > 0 ? (
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={equity}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="timestamp" fontSize={11} />
                  <YAxis fontSize={11} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="equity"
                    stroke="#1677ff"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <ReferenceLine
                    y={risk?.equity_high_watermark}
                    stroke="#faad14"
                    strokeDasharray="5 5"
                    label="高水位"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState description="暂无权益数据" detail="Bot 启动后将开始记录每日权益曲线" />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="风控状态">
            {risk ? (
              <>
                <Statistic
                  title="高水位线"
                  value={risk.equity_high_watermark ?? 0}
                  precision={2}
                  suffix="USDT"
                  prefix={<DollarOutlined />}
                />
                <Statistic
                  title="当前回撤"
                  value={risk.equity_high_watermark && risk.equity_high_watermark > 0
                    ? ((1 - (estimatedTotal ?? risk.equity_high_watermark) / risk.equity_high_watermark) * 100)
                    : 0}
                  precision={2}
                  suffix="%"
                  valueStyle={{
                    color: risk.max_drawdown_pct && risk.max_drawdown_pct > 10 ? '#ff4d4f' : '#52c41a',
                  }}
                  style={{ marginTop: 16 }}
                />
              </>
            ) : (
              <EmptyState description="暂无风控数据" />
            )}
          </Card>
        </Col>
      </Row>

      {/* 持仓表格 */}
      <Card
        title={
          <span>
            {status?.bot_running && status?.dry_run ? '模拟持仓（dry-run）' : '当前持仓'}
            {positionCount > 0 && (
              <Tag style={{ marginLeft: 8 }} color="blue">{positionCount} 个</Tag>
            )}
          </span>
        }
        extra={status?.bot_running && status?.dry_run ? <Tag color="blue">DRY-RUN</Tag> : undefined}
        style={{ marginTop: 16 }}
      >
        <Table
          dataSource={positions}
          rowKey={(r) => `${r.symbol}-${r.side}`}
          pagination={false}
          size="middle"
          scroll={{ x: 720 }}
          locale={{
            emptyText: status?.bot_running
              ? '暂无持仓，等待策略开仓…'
              : 'Bot 未运行或无持仓',
          }}
          columns={[
            {
              title: '币种',
              dataIndex: 'symbol',
              key: 'symbol',
              width: 100,
            },
            {
              title: '方向',
              dataIndex: 'side',
              key: 'side',
              width: 70,
              render: (s: string) => (
                <Tag color={s === 'long' ? 'green' : 'red'}>
                  {s === 'long' ? '多' : '空'}
                </Tag>
              ),
            },
            {
              title: '数量',
              dataIndex: 'contracts',
              key: 'contracts',
              ...numAlign,
              width: 100,
              render: (v: number) => v?.toFixed(4),
            },
            {
              title: '开仓价',
              dataIndex: 'entry_price',
              key: 'entry_price',
              ...numAlign,
              width: 100,
              render: (v: number) => v?.toFixed(2),
            },
            {
              title: '标记价',
              dataIndex: 'mark_price',
              key: 'mark_price',
              ...numAlign,
              width: 100,
              render: (v: number) => v?.toFixed(2),
            },
            {
              title: '杠杆',
              dataIndex: 'leverage',
              key: 'leverage',
              ...numAlign,
              width: 70,
              render: (v: number) => `${v}x`,
            },
            {
              title: '未实现盈亏',
              dataIndex: 'unrealized_pnl',
              key: 'unrealized_pnl',
              ...numAlign,
              width: 120,
              render: (v: number) => (
                <span style={{ color: pnlColor(v), fontWeight: 500 }}>
                  {v >= 0 ? '+' : ''}{v.toFixed(2)} USDT
                </span>
              ),
            },
            {
              title: '强平价',
              dataIndex: 'liquidation_price',
              key: 'liquidation_price',
              ...numAlign,
              width: 100,
              render: (v: number) => v?.toFixed(2) ?? '-',
            },
          ]}
        />
      </Card>
    </div>
  )
}
