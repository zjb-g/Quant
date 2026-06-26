import { useState, useEffect } from 'react'
import { Card, Table, Tag, Select, Space, Badge } from 'antd'
import { apiClient, type AlertEvent } from '../api/client'

const LEVEL_COLOR: Record<string, string> = {
  INFO: 'blue',
  WARNING: 'orange',
  CRITICAL: 'red',
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertEvent[]>([])
  const [levelFilter, setLevelFilter] = useState<string | undefined>()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiClient.getAlerts(200)
        setAlerts(data)
      } catch {
        // mock 占位
        setAlerts([
          {
            id: '1',
            timestamp: new Date().toISOString(),
            level: 'INFO',
            type: 'order_submitted',
            message: 'BTC/USDT:USDT 限价单 0.01 BTC @ 60000 (dry-run)',
          },
          {
            id: '2',
            timestamp: new Date(Date.now() - 60000).toISOString(),
            level: 'WARNING',
            type: 'liquidation_warning',
            message: 'ETH/USDT:USDT 强平距离 8.5%（阈值 10%）',
          },
        ])
      } finally {
        setLoading(false)
      }
    }
    load()
    const timer = setInterval(load, 15000)
    return () => clearInterval(timer)
  }, [])

  const filtered = levelFilter
    ? alerts.filter((a) => a.level === levelFilter)
    : alerts

  const criticalCount = alerts.filter((a) => a.level === 'CRITICAL').length
  const warningCount = alerts.filter((a) => a.level === 'WARNING').length

  return (
    <div>
      <Card
        title={
          <Space>
            <span>告警事件</span>
            <Badge count={criticalCount} overflowCount={99} />
            <Tag color="red">CRITICAL: {criticalCount}</Tag>
            <Tag color="orange">WARNING: {warningCount}</Tag>
            <Tag color="blue">INFO: {alerts.length - criticalCount - warningCount}</Tag>
          </Space>
        }
        extra={
          <Select
            allowClear
            placeholder="按级别筛选"
            style={{ width: 150 }}
            value={levelFilter}
            onChange={setLevelFilter}
            options={[
              { label: 'CRITICAL', value: 'CRITICAL' },
              { label: 'WARNING', value: 'WARNING' },
              { label: 'INFO', value: 'INFO' },
            ]}
          />
        }
      >
        <Table
          dataSource={filtered}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 50 }}
          scroll={{ x: 700 }}
          columns={[
            {
              title: '时间',
              dataIndex: 'timestamp',
              key: 'timestamp',
              width: 180,
              render: (t: string) => new Date(t).toLocaleString('zh-CN'),
            },
            {
              title: '级别',
              dataIndex: 'level',
              key: 'level',
              width: 100,
              render: (l: string) => <Tag color={LEVEL_COLOR[l]}>{l}</Tag>,
            },
            { title: '类型', dataIndex: 'type', key: 'type', width: 180 },
            { title: '消息', dataIndex: 'message', key: 'message' },
          ]}
        />
      </Card>
    </div>
  )
}
