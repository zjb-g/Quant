import { useState, useEffect } from 'react'
import { Card, Button, Space, Input, Form, InputNumber, message, Modal, Tag, Statistic, Row, Col, Divider } from 'antd'
import { PlayCircleOutlined, PauseCircleOutlined, StopOutlined, ThunderboltOutlined, SaveOutlined } from '@ant-design/icons'
import { apiClient, type RiskConfig, type RiskState } from '../api/client'

export default function ControlPage() {
  const [riskState, setRiskState] = useState<RiskState | null>(null)
  const [config, setConfig] = useState<RiskConfig | null>(null)
  const [form] = Form.useForm<RiskConfig>()
  const [killReason, setKillReason] = useState('')
  const [loading, setLoading] = useState(false)

  const load = async () => {
    try {
      const [r, c] = await Promise.all([
        apiClient.getRiskState(),
        apiClient.getRiskConfig(),
      ])
      setRiskState(r)
      setConfig(c)
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
      await apiClient.startBot()
      message.success('Bot 已启动')
      load()
    } catch {
      message.error('启动失败')
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
        <Col span={12}>
          <Card title="Bot 控制">
            <Space size="large">
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleStart}
                loading={loading}
                size="large"
              >
                启动
              </Button>
              <Button
                danger
                icon={<PauseCircleOutlined />}
                onClick={handleStop}
                loading={loading}
                size="large"
              >
                停止
              </Button>
            </Space>
            <Divider />
            <Row gutter={16}>
              <Col span={8}>
                <Statistic
                  title="Bot 状态"
                  value={riskState?.kill_switch ? 'KILL SWITCH' : '正常'}
                  valueStyle={{ color: riskState?.kill_switch ? '#cf1322' : '#3f8600' }}
                />
              </Col>
              <Col span={8}>
                <Statistic title="总敞口" value={riskState?.current_total_notional ?? 0} precision={2} suffix="USDT" />
              </Col>
              <Col span={8}>
                <Statistic title="最大杠杆" value={riskState?.max_leverage ?? 0} suffix="x" />
              </Col>
            </Row>
          </Card>
        </Col>
        <Col span={12}>
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

      <Card title="风控参数配置" style={{ marginTop: 16 }}>
        <Form form={form} layout="inline">
          <Row gutter={[16, 16]} style={{ width: '100%' }}>
            <Col span={6}>
              <Form.Item name="max_single_order_notional" label="单笔上限">
                <InputNumber addonAfter="USDT" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="max_symbol_notional" label="单币敞口">
                <InputNumber addonAfter="USDT" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="max_total_notional" label="总敞口">
                <InputNumber addonAfter="USDT" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="max_leverage" label="最大杠杆">
                <InputNumber addonAfter="x" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="max_drawdown_stop_pct" label="回撤熔断">
                <InputNumber addonAfter="%" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="daily_loss_stop_pct" label="日亏限额">
                <InputNumber addonAfter="%" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="liquidation_distance_pct" label="强平距离">
                <InputNumber addonAfter="%" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
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
