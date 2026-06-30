import { useState, useEffect } from 'react'
import { Card, Button, Space, Input, Form, InputNumber, message, Modal, Tag, Statistic, Row, Col, Divider, Select, Alert, Table } from 'antd'
import { PlayCircleOutlined, PauseCircleOutlined, StopOutlined, ThunderboltOutlined, SaveOutlined, ReloadOutlined } from '@ant-design/icons'
import { apiClient, type RiskConfig, type RiskState, type BotStatus, type Position } from '../api/client'
import { useStrategies } from '../hooks/useStrategies'

export default function ControlPage() {
  const [riskState, setRiskState] = useState<RiskState | null>(null)
  const [config, setConfig] = useState<RiskConfig | null>(null)
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null)
  const [dryRunPositions, setDryRunPositions] = useState<Position[]>([])
  const {
    selected: runStrategy,
    setSelected: setRunStrategy,
    loading: strategiesLoading,
    error: strategiesError,
    options: strategyOptions,
    refresh: refreshStrategies,
    runnableCount,
  } = useStrategies('EmaCrossoverStrategy')
  const [form] = Form.useForm<RiskConfig>()
  const [killReason, setKillReason] = useState('')
  const [loading, setLoading] = useState(false)

  const load = async () => {
    try {
      const [r, c, b, p] = await Promise.all([
        apiClient.getRiskState(),
        apiClient.getRiskConfig(),
        apiClient.getBotStatus(),
        apiClient.getPositions().catch(() => []),
      ])
      setRiskState(r)
      setConfig(c)
      setBotStatus(b)
      setDryRunPositions(p)
      form.setFieldsValue(c)
    } catch {
      message.warning('后端未连接')
    }
  }

  useEffect(() => {
    load()
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [])

  const handleStart = async () => {
    setLoading(true)
    try {
      await apiClient.startBot(runStrategy)
      message.success(`Freqtrade dry-run 已启动（${runStrategy}）`)
      load()
    } catch (err: unknown) {
      const res = (err as { response?: { status?: number; data?: { detail?: string } } })?.response
      const msg = res?.data?.detail
      if (res?.status === 409) {
        message.warning(msg || 'Bot 已在运行中，请刷新页面查看状态')
      } else {
        message.error(msg || '启动失败（若等待较久，请刷新页面确认 Bot 是否已启动）')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    try {
      await apiClient.stopBot()
      message.success('Bot 已停止')
      load()
    } catch {
      message.error('停止失败')
    } finally {
      setLoading(false)
    }
  }

  const handleKillSwitch = async () => {
    Modal.confirm({
      title: '激活 Kill Switch',
      content: (
        <Input
          placeholder="激活原因（可选）"
          onChange={(e) => setKillReason(e.target.value)}
        />
      ),
      okText: '确认激活',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await apiClient.activateKillSwitch(killReason || 'manual')
          message.success('Kill Switch 已激活')
          load()
        } catch {
          message.error('激活失败')
        }
      },
    })
  }

  const handleEmergencyClose = () => {
    Modal.confirm({
      title: '⚠️ 紧急全平',
      content: '此操作将平仓所有持仓。首次点击进入确认流程。',
      okText: '我要全平',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        Modal.confirm({
          title: '二次确认 - 紧急全平',
          content: '确定要真实平仓所有持仓吗？此操作不可撤销！',
          okText: '确认全平',
          okType: 'danger',
          cancelText: '取消',
          onOk: async () => {
            try {
              await apiClient.emergencyCloseAll(true)
              message.success('紧急全平指令已发送')
              load()
            } catch {
              message.error('全平失败')
            }
          },
        })
      },
    })
  }

  const handleSaveConfig = async () => {
    try {
      const values = await form.validateFields()
      await apiClient.updateRiskConfig(values)
      message.success('风控参数已保存')
      load()
    } catch {
      message.error('保存失败')
    }
  }

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card title="Bot 控制（Freqtrade dry-run）">
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message="启动后会运行 Freqtrade 模拟盘（dry_run=true），使用 OKX 行情，不会真实下单。"
            />
            {strategiesError && (
              <Alert
                type="error"
                showIcon
                style={{ marginBottom: 12 }}
                message="策略列表加载失败"
                description={strategiesError}
                action={(
                  <Button size="small" onClick={() => void refreshStrategies()}>
                    重试
                  </Button>
                )}
              />
            )}
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Space wrap style={{ width: '100%', justifyContent: 'space-between' }}>
                <span style={{ color: '#999', fontSize: 13 }}>
                  与「策略管理」共用同一列表 · 可运行 {runnableCount} 个
                </span>
                <Button
                  size="small"
                  icon={<ReloadOutlined />}
                  loading={strategiesLoading}
                  onClick={() => void refreshStrategies()}
                >
                  刷新策略
                </Button>
              </Space>
              <Select
                showSearch
                optionFilterProp="label"
                style={{ width: '100%' }}
                value={runStrategy}
                onChange={setRunStrategy}
                disabled={botStatus?.running || strategiesLoading}
                loading={strategiesLoading}
                placeholder="选择策略（类名）"
                options={strategyOptions}
                notFoundContent={strategiesLoading ? '加载中…' : '暂无可用策略，请先在策略管理中添加'}
              />
              <Space wrap size="middle">
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={handleStart}
                  loading={loading}
                  disabled={botStatus?.running}
                  size="large"
                >
                  启动
                </Button>
                <Button
                  danger
                  icon={<PauseCircleOutlined />}
                  onClick={handleStop}
                  loading={loading}
                  disabled={!botStatus?.running}
                  size="large"
                >
                  停止
                </Button>
              </Space>
            </Space>
            <Divider />
            <Row gutter={16}>
              <Col xs={24} sm={8}>
                <Statistic
                  title="运行状态"
                  value={botStatus?.running ? '运行中' : '已停止'}
                  valueStyle={{ color: botStatus?.running ? '#3f8600' : '#999' }}
                />
              </Col>
              <Col xs={24} sm={8}>
                <Statistic title="进程 PID" value={botStatus?.pid ?? '-'} />
              </Col>
              <Col xs={24} sm={8}>
                <Statistic title="策略" value={botStatus?.strategy ?? '-'} valueStyle={{ fontSize: 14 }} />
              </Col>
            </Row>
            {botStatus?.log_tail && botStatus.log_tail.length > 0 && (
              <pre style={{
                marginTop: 12, padding: 8, background: '#111', color: '#aaa',
                fontSize: 11, maxHeight: 120, overflow: 'auto', borderRadius: 4,
              }}>
                {botStatus.log_tail.slice(-8).join('\n')}
              </pre>
            )}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="紧急操作">
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              <Button
                block
                danger
                icon={<StopOutlined />}
                onClick={handleKillSwitch}
                size="large"
                disabled={riskState?.kill_switch}
              >
                {riskState?.kill_switch ? 'Kill Switch 已激活' : '激活 Kill Switch'}
              </Button>
              {riskState?.kill_switch_reason && (
                <Tag color="red">原因：{riskState.kill_switch_reason}</Tag>
              )}
              <Button
                block
                danger
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={handleEmergencyClose}
                size="large"
              >
                紧急全平（需二次确认）
              </Button>
              <div style={{ fontSize: 12, color: '#999' }}>
                Kill Switch 激活后禁止开新仓，仅允许 reduce-only 平仓。
                紧急全平需经过两次确认才会真实执行。
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      {(botStatus?.running || dryRunPositions.length > 0) && botStatus?.dry_run !== false && (
        <Card
          title="模拟盘持仓（dry-run）"
          style={{ marginTop: 16 }}
          extra={(
            <Tag color="blue">
              钱包 {botStatus.dryrun_summary?.wallet_balance?.toFixed(2) ?? '-'} USDT
            </Tag>
          )}
        >
          {botStatus.dryrun_summary && (
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col xs={12} sm={6}>
                <Statistic title="开仓笔数" value={botStatus.dryrun_summary.open_trades} />
              </Col>
              <Col xs={12} sm={6}>
                <Statistic
                  title="未实现盈亏"
                  value={botStatus.dryrun_summary.total_unrealized_pnl}
                  precision={2}
                  suffix="U"
                  valueStyle={{
                    color: botStatus.dryrun_summary.total_unrealized_pnl >= 0 ? '#3f8600' : '#cf1322',
                  }}
                />
              </Col>
              <Col xs={12} sm={6}>
                <Statistic
                  title="已实现盈亏"
                  value={botStatus.dryrun_summary.total_realized_pnl}
                  precision={2}
                  suffix="U"
                />
              </Col>
              <Col xs={12} sm={6}>
                <Statistic
                  title="占用保证金"
                  value={botStatus.dryrun_summary.total_stake}
                  precision={2}
                  suffix="U"
                />
              </Col>
            </Row>
          )}
          <Table
            dataSource={dryRunPositions}
            rowKey={(r) => `${r.symbol}-${r.side}`}
            size="small"
            pagination={false}
            scroll={{ x: 720 }}
            locale={{ emptyText: '暂无模拟持仓，策略开仓后会显示在这里' }}
            columns={[
              { title: '币种', dataIndex: 'symbol', key: 'symbol' },
              {
                title: '方向', dataIndex: 'side', key: 'side',
                render: (s: string) => <Tag color={s === 'long' ? 'green' : 'red'}>{s === 'long' ? '多' : '空'}</Tag>,
              },
              { title: '数量', dataIndex: 'contracts', key: 'contracts', render: (v: number) => v?.toFixed(4) },
              { title: '开仓价', dataIndex: 'entry_price', key: 'entry', render: (v: number) => v?.toFixed(2) },
              { title: '标记价', dataIndex: 'mark_price', key: 'mark', render: (v: number) => v?.toFixed(2) },
              { title: '杠杆', dataIndex: 'leverage', key: 'lev', render: (v: number) => `${v}x` },
              {
                title: '未实现盈亏', dataIndex: 'unrealized_pnl', key: 'pnl',
                render: (v: number) => (
                  <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>
                    {v >= 0 ? '+' : ''}{v?.toFixed(2)} U
                  </span>
                ),
              },
            ]}
          />
        </Card>
      )}

      <Card title="风控参数配置" style={{ marginTop: 16 }}>
        <Form form={form} layout="inline">
          <Row gutter={[16, 16]} style={{ width: '100%' }}>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="max_single_order_notional" label="单笔上限">
                <InputNumber addonAfter="USDT" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="max_symbol_notional" label="单币敞口">
                <InputNumber addonAfter="USDT" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="max_total_notional" label="总敞口">
                <InputNumber addonAfter="USDT" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="max_leverage" label="最大杠杆">
                <InputNumber addonAfter="x" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="max_drawdown_stop_pct" label="回撤熔断">
                <InputNumber addonAfter="%" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="daily_loss_stop_pct" label="日亏限额">
                <InputNumber addonAfter="%" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="liquidation_distance_pct" label="强平距离">
                <InputNumber addonAfter="%" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item>
                <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveConfig}>
                  保存配置
                </Button>
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Card>
    </div>
  )
}
