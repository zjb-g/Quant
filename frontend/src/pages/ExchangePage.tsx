import { useState, useEffect } from 'react'
import {
  Card, Button, Input, Space, Tag, message, Table, Statistic, Row, Col,
  Alert, Form, Descriptions, Tabs, Spin
} from 'antd'
import {
  ApiOutlined, LinkOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ReloadOutlined, WalletOutlined
} from '@ant-design/icons'
import { apiClient, type Position, type PositionHistory, type HistoricalTrade } from '../api/client'

const CLOSE_TYPE_LABELS: Record<string, string> = {
  partial: '部分平仓',
  full: '完全平仓',
  liquidation: '强平',
  forced_reduction: '强减',
  adl: 'ADL',
  unknown: '未知',
}

export default function ExchangePage() {
  const [connected, setConnected] = useState(false)
  const [exchangeName, setExchangeName] = useState('')
  const [error, setError] = useState('')
  const [envStatus, setEnvStatus] = useState<Record<string, boolean>>({})
  const [balance, setBalance] = useState<{total: number; free: number; used: number; currency: string} | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [positionHistory, setPositionHistory] = useState<PositionHistory[]>([])
  const [trades, setTrades] = useState<HistoricalTrade[]>([])
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

  const loadStatus = async () => {
    try {
      const [status, env] = await Promise.all([
        apiClient.getExchangeStatus(),
        apiClient.getEnvStatus(),
      ])
      setConnected(status.connected)
      setExchangeName(status.exchange)
      setError(status.error)
      setEnvStatus(env)
    } catch {
      // 后端未连接
    }
  }

  useEffect(() => { loadStatus() }, [])

  const handleConnect = async (values: any) => {
    setLoading(true)
    try {
      const vars: Record<string, string> = {}
      if (values.okx_key) vars.OKX_API_KEY = values.okx_key
      if (values.okx_secret) vars.OKX_API_SECRET = values.okx_secret
      if (values.okx_pass) vars.OKX_API_PASSPHRASE = values.okx_pass
      if (values.gate_key) vars.GATE_API_KEY = values.gate_key
      if (values.gate_secret) vars.GATE_API_SECRET = values.gate_secret

      const result = await apiClient.testExchange(vars)
      setConnected(result.connected)
      setExchangeName(result.exchange)
      setError(result.error)

      if (result.connected) {
        message.success(`交易所 ${result.exchange} 连接成功！`)
        loadData()
      } else {
        message.error(result.error || '连接失败')
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || '连接失败')
    } finally {
      setLoading(false)
    }
  }

  const loadData = async () => {
    setLoading(true)
    try {
      const [bal, pos, hist, tr] = await Promise.all([
        apiClient.getExchangeBalance().catch(() => null),
        apiClient.getExchangePositions().catch(() => []),
        apiClient.getExchangePositionsHistory(50, true).catch(() => []),
        apiClient.getExchangeTrades(50).catch(() => []),
      ])
      setBalance(bal)
      setPositions(pos)
      setPositionHistory(hist)
      setTrades(tr)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (connected) loadData()
  }, [connected])

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card title={<span><ApiOutlined /> 交易所连接</span>}>
            <div style={{ marginBottom: 16 }}>
              {connected ? (
                <Tag icon={<CheckCircleOutlined />} color="success" style={{ fontSize: 14, padding: '4px 12px' }}>
                  已连接: {exchangeName}
                </Tag>
              ) : (
                <Tag icon={<CloseCircleOutlined />} color="error" style={{ fontSize: 14, padding: '4px 12px' }}>
                  未连接
                </Tag>
              )}
            </div>
            {error && <Alert message={error} type="error" style={{ marginBottom: 16 }} />}
            <Button icon={<ReloadOutlined />} onClick={loadStatus} block>刷新状态</Button>
          </Card>
        </Col>
        <Col span={16}>
          <Card title={<span><LinkOutlined /> 配置 API Key</span>}>
            <Alert
              message="API Key 仅保存在内存中，不会写入文件或代码库。重启后需重新输入。"
              type="warning"
              style={{ marginBottom: 16 }}
            />
            <Form form={form} layout="vertical" onFinish={handleConnect}>
              <Form.Item label="OKX API Key" name="okx_key">
                <Input.Password placeholder={envStatus.OKX_API_KEY ? '已配置（输入新值覆盖）' : '输入 OKX API Key'} />
              </Form.Item>
              <Form.Item label="OKX API Secret" name="okx_secret">
                <Input.Password placeholder={envStatus.OKX_API_SECRET ? '已配置' : '输入 OKX API Secret'} />
              </Form.Item>
              <Form.Item label="OKX Passphrase" name="okx_pass">
                <Input.Password placeholder={envStatus.OKX_API_PASSPHRASE ? '已配置' : '输入 OKX Passphrase'} />
              </Form.Item>
              <Form.Item label="Gate API Key（备用）" name="gate_key">
                <Input.Password placeholder={envStatus.GATE_API_KEY ? '已配置' : '输入 Gate API Key'} />
              </Form.Item>
              <Form.Item label="Gate API Secret（备用）" name="gate_secret">
                <Input.Password placeholder={envStatus.GATE_API_SECRET ? '已配置' : '输入 Gate API Secret'} />
              </Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" loading={loading} icon={<LinkOutlined />}>
                  连接并测试
                </Button>
                {connected && (
                  <Button onClick={loadData} icon={<ReloadOutlined />}>刷新数据</Button>
                )}
              </Space>
            </Form>
          </Card>
        </Col>
      </Row>

      {connected && (
        <Tabs
          defaultActiveKey="balance"
          style={{ marginTop: 16 }}
          items={[
            {
              key: 'balance',
              label: '账户余额',
              children: (
                <Card>
                  {balance ? (
                    <Row gutter={16}>
                      <Col span={8}>
                        <Statistic title="总余额" value={balance.total} precision={2} suffix={balance.currency} />
                      </Col>
                      <Col span={8}>
                        <Statistic title="可用余额" value={balance.free} precision={2} suffix={balance.currency} />
                      </Col>
                      <Col span={8}>
                        <Statistic title="已用保证金" value={balance.used} precision={2} suffix={balance.currency} />
                      </Col>
                    </Row>
                  ) : (
                    <Spin tip="加载中..." />
                  )}
                </Card>
              ),
            },
            {
              key: 'positions',
              label: `当前持仓 (${positions.length})`,
              children: (
                <Card>
                  <Table
                    dataSource={positions}
                    rowKey={(r) => `${r.symbol}-${r.side}`}
                    size="small"
                    pagination={false}
                    columns={[
                      { title: '币种', dataIndex: 'symbol', key: 'symbol' },
                      {
                        title: '方向', dataIndex: 'side', key: 'side',
                        render: (s: string) => <Tag color={s === 'long' ? 'green' : 'red'}>{s}</Tag>,
                      },
                      { title: '数量', dataIndex: 'contracts', key: 'contracts', render: (v: number) => v?.toFixed(4) },
                      { title: '开仓价', dataIndex: 'entry_price', key: 'entry_price', render: (v: number) => v?.toFixed(2) },
                      { title: '标记价', dataIndex: 'mark_price', key: 'mark_price', render: (v: number) => v?.toFixed(2) },
                      { title: '杠杆', dataIndex: 'leverage', key: 'leverage', render: (v: number) => `${v}x` },
                      {
                        title: '未实现盈亏', dataIndex: 'unrealized_pnl', key: 'pnl',
                        render: (v: number) => (
                          <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>
                            {v >= 0 ? '+' : ''}{v?.toFixed(2)}
                          </span>
                        ),
                      },
                      { title: '强平价', dataIndex: 'liquidation_price', key: 'liq' },
                    ]}
                  />
                </Card>
              ),
            },
            {
              key: 'position-history',
              label: `历史持仓 (${positionHistory.length})`,
              children: (
                <Card>
                  <Table
                    dataSource={positionHistory}
                    rowKey={(r) => `${r.position_id}::${r.close_time}`}
                    size="small"
                    pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
                    columns={[
                      { title: '平仓时间', dataIndex: 'close_time', key: 'close_time', width: 180,
                        render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-' },
                      { title: '币种', dataIndex: 'symbol', key: 'symbol' },
                      {
                        title: '方向', dataIndex: 'side', key: 'side',
                        render: (s: string) => <Tag color={s === 'long' ? 'green' : 'red'}>{s}</Tag>,
                      },
                      { title: '杠杆', dataIndex: 'leverage', key: 'leverage', render: (v: number) => `${v}x` },
                      { title: '开仓价', dataIndex: 'open_avg_price', key: 'open', render: (v: number) => v?.toFixed(2) },
                      { title: '平仓价', dataIndex: 'close_avg_price', key: 'close', render: (v: number) => v?.toFixed(2) },
                      { title: '数量', dataIndex: 'close_size', key: 'size', render: (v: number) => v?.toFixed(4) },
                      {
                        title: '盈亏', dataIndex: 'pnl', key: 'pnl',
                        render: (v: number) => (
                          <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>
                            {v >= 0 ? '+' : ''}{v?.toFixed(4)}
                          </span>
                        ),
                      },
                      {
                        title: '类型', dataIndex: 'close_type', key: 'type',
                        render: (t: string) => (
                          <Tag color={t === 'liquidation' ? 'red' : t === 'full' ? 'blue' : 'default'}>
                            {CLOSE_TYPE_LABELS[t] || t}
                          </Tag>
                        ),
                      },
                      { title: '手续费', dataIndex: 'fee', key: 'fee', render: (v: number) => v?.toFixed(4) },
                    ]}
                  />
                </Card>
              ),
            },
            {
              key: 'trades',
              label: `历史交易 (${trades.length})`,
              children: (
                <Card>
                  <Table
                    dataSource={trades}
                    rowKey="id"
                    size="small"
                    pagination={{ pageSize: 20 }}
                    columns={[
                      { title: '时间', dataIndex: 'timestamp', key: 'ts', width: 180,
                        render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-' },
                      { title: '币种', dataIndex: 'symbol', key: 'sym' },
                      {
                        title: '方向', dataIndex: 'side', key: 'side',
                        render: (s: string) => <Tag color={s === 'buy' ? 'green' : 'red'}>{s}</Tag>,
                      },
                      { title: '数量', dataIndex: 'amount', key: 'amt' },
                      { title: '价格', dataIndex: 'price', key: 'px' },
                      { title: '手续费', dataIndex: 'fee', key: 'fee' },
                    ]}
                  />
                </Card>
              ),
            },
          ]}
        />
      )}
    </div>
  )
}
