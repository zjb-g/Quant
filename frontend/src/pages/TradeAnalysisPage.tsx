import { useCallback, useEffect, useState } from 'react'
import {
  Card, Row, Col, Statistic, Table, Tag, Space, Button, Spin, message, Alert,
  DatePicker, Select, Modal, Typography,
} from 'antd'
import { BarChartOutlined, RobotOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import type { Dayjs } from 'dayjs'
import {
  apiClient,
  type TradeAnalysisStats,
  type TradeBucketStats,
} from '../api/client'
import EmptyState from '../components/EmptyState'
import { pnlColor, numAlign } from '../theme'

const { RangePicker } = DatePicker
const { Paragraph } = Typography

function BucketTable({ title, data }: { title: string; data: TradeBucketStats[] }) {
  return (
    <Card title={title} size="small" style={{ marginBottom: 16 }}>
      <Table
        dataSource={data}
        rowKey="label"
        size="small"
        pagination={false}
        columns={[
          { title: '分组', dataIndex: 'label' },
          { title: '笔数', dataIndex: 'count', width: 70, ...numberColumnStyle },
          {
            title: '胜率', dataIndex: 'win_rate', width: 80,
            ...numAlign,
            render: (v: number) => `${v.toFixed(1)}%`,
          },
          {
            title: '总盈亏', dataIndex: 'total_pnl',
            ...numAlign,
            render: (v: number) => (
              <span style={{ color: pnlColor(v), fontWeight: 500 }}>{v.toFixed(2)}</span>
            ),
          },
          {
            title: '均盈亏', dataIndex: 'avg_pnl',
            ...numAlign,
            render: (v: number) => v.toFixed(4),
          },
        ]}
      />
    </Card>
  )
}

export default function TradeAnalysisPage() {
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<TradeAnalysisStats | null>(null)
  const [filteredCount, setFilteredCount] = useState(0)
  const [totalCount, setTotalCount] = useState(0)
  const [timeRange, setTimeRange] = useState<[Dayjs, Dayjs] | null>(null)
  const [side, setSide] = useState<string | undefined>()
  const [aiConfigured, setAiConfigured] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [aiText, setAiText] = useState('')

  const loadAnalysis = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.analyzePositionsHistory({
        side,
        startTime: timeRange?.[0]?.startOf('day').toISOString(),
        endTime: timeRange?.[1]?.endOf('day').toISOString(),
      })
      setStats(res.stats)
      setFilteredCount(res.filtered_count)
      setTotalCount(res.total_count)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(msg || '加载分析数据失败')
      setStats(null)
    } finally {
      setLoading(false)
    }
  }, [timeRange, side])

  useEffect(() => {
    loadAnalysis()
    apiClient.aiStatus().then((s) => setAiConfigured(s.configured)).catch(() => {})
  }, [loadAnalysis])

  const runAiAnalysis = async () => {
    setAiLoading(true)
    setAiModalOpen(true)
    setAiText('')
    try {
      const res = await apiClient.aiAnalyzeTrades({
        side,
        startTime: timeRange?.[0]?.startOf('day').toISOString(),
        endTime: timeRange?.[1]?.endOf('day').toISOString(),
      })
      setAiText(res.analysis)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(msg || 'AI 分析失败')
      setAiModalOpen(false)
    } finally {
      setAiLoading(false)
    }
  }

  const sideChartData = stats?.by_side.map((b) => ({
    name: b.label,
    胜率: b.win_rate,
    笔数: b.count,
    盈亏: b.total_pnl,
  })) ?? []

  const leverageChartData = stats?.by_leverage.map((b) => ({
    name: b.label,
    胜率: b.win_rate,
    盈亏: b.total_pnl,
  })) ?? []

  return (
    <div>
      <Card
        title={<span><BarChartOutlined style={{ marginRight: 8 }} />持仓历史分析</span>}
        extra={
          <Space wrap>
            <RangePicker
              value={timeRange}
              onChange={(v) => setTimeRange(v as [Dayjs, Dayjs] | null)}
              placeholder={['开始', '结束']}
            />
            <Select
              allowClear
              placeholder="方向"
              style={{ width: 100 }}
              value={side}
              onChange={setSide}
              options={[
                { value: 'long', label: '做多' },
                { value: 'short', label: '做空' },
              ]}
            />
            <Button icon={<ReloadOutlined />} onClick={loadAnalysis} loading={loading}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<RobotOutlined />}
              onClick={runAiAnalysis}
              loading={aiLoading}
              disabled={!aiConfigured || !stats?.total_trades}
            >
              AI 深度分析
            </Button>
          </Space>
        }
      >
        {!aiConfigured && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="未配置 DEEPSEEK_API_KEY，AI 分析不可用。可在 .env 中配置后重启后端。"
          />
        )}
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={`基于 OKX 实盘历史持仓 · 当前分析 ${filteredCount} 笔（总计 ${totalCount} 笔）`}
        />

        <Spin spinning={loading}>
          {!loading && (!stats || stats.total_trades === 0) && (
            <EmptyState
              description="暂无历史持仓数据"
              detail="或筛选条件下无记录，请调整筛选条件或确认交易所已连接并拉取了历史数据"
            />
          )}

          {stats && stats.total_trades > 0 && (
            <>
              {/* 核心指标 */}
              <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                <Col xs={12} sm={8} md={4}>
                  <Card><Statistic title="总交易" value={stats.total_trades} /></Card>
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Card>
                    <Statistic
                      title="胜率"
                      value={stats.win_rate}
                      precision={1}
                      suffix="%"
                      valueStyle={{
                        color: stats.win_rate >= 50 ? '#52c41a' : '#ff4d4f',
                      }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Card>
                    <Statistic
                      title="总盈亏"
                      value={stats.total_pnl}
                      precision={2}
                      suffix="U"
                      valueStyle={{ color: pnlColor(stats.total_pnl) }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Card>
                    <Statistic
                      title="盈亏比"
                      value={stats.profit_factor}
                      precision={2}
                      valueStyle={{
                        color: stats.profit_factor >= 1 ? '#52c41a' : '#ff4d4f',
                      }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Card>
                    <Statistic
                      title="均持仓(h)"
                      value={stats.avg_holding_hours}
                      precision={1}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Card>
                    <Statistic
                      title="费用合计"
                      value={stats.total_fee + stats.total_funding_fee}
                      precision={2}
                      suffix="U"
                    />
                  </Card>
                </Col>
              </Row>

              {/* 图表 */}
              <Row gutter={[16, 16]}>
                <Col xs={24} md={12}>
                  <Card title="多空胜率对比" size="small">
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={sideChartData}>
                        <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                        <XAxis dataKey="name" />
                        <YAxis yAxisId="left" />
                        <YAxis yAxisId="right" orientation="right" />
                        <Tooltip />
                        <Legend />
                        <Bar yAxisId="left" dataKey="胜率" fill="#1677ff" name="胜率%" radius={[4, 4, 0, 0]} />
                        <Bar yAxisId="right" dataKey="盈亏" fill="#52c41a" name="盈亏U" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>
                </Col>
                <Col xs={24} md={12}>
                  <Card title="杠杆分组表现" size="small">
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={leverageChartData}>
                        <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="胜率" fill="#722ed1" name="胜率%" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="盈亏" fill="#fa8c16" name="盈亏U" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>
                </Col>
              </Row>

              {/* 分组表格 */}
              <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
                <Col xs={24} md={12}>
                  <BucketTable title="持仓时长分组" data={stats.by_holding} />
                </Col>
                <Col xs={24} md={12}>
                  <BucketTable title="平仓类型分组" data={stats.by_close_type} />
                </Col>
              </Row>

              <Row gutter={[16, 16]}>
                <Col xs={24} md={12}>
                  <Card title="最佳 / 最差单笔" size="small">
                    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>最大盈利：</span>
                        <Tag color="success">{stats.max_win.toFixed(4)} USDT</Tag>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>最大亏损：</span>
                        <Tag color="error">{stats.max_loss.toFixed(4)} USDT</Tag>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>平均盈利：</span>
                        <Tag color="success">{stats.avg_win.toFixed(4)} USDT</Tag>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>平均亏损：</span>
                        <Tag color="error">{stats.avg_loss.toFixed(4)} USDT</Tag>
                      </div>
                    </Space>
                  </Card>
                </Col>
                <Col xs={24} md={12}>
                  <BucketTable title="币种分布" data={stats.by_symbol} />
                </Col>
              </Row>
            </>
          )}
        </Spin>
      </Card>

      {/* AI 分析 Modal */}
      <Modal
        title={<span><RobotOutlined /> AI 交易模式分析</span>}
        open={aiModalOpen}
        onCancel={() => setAiModalOpen(false)}
        footer={null}
        width={760}
      >
        <Spin spinning={aiLoading} tip="AI 正在分析交易模式...">
          <Paragraph style={{ whiteSpace: 'pre-wrap', maxHeight: '60vh', overflow: 'auto' }}>
            {aiText || '分析中，请稍候...'}
          </Paragraph>
        </Spin>
      </Modal>
    </div>
  )
}
