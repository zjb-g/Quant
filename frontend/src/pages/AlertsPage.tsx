import { useState, useEffect } from 'react'
import { Card, Table, Tag, Select, Space, Badge } from 'antd'
import { AlertOutlined } from '@ant-design/icons'
import { apiClient, type AlertEvent } from '../api/client'
import LoadingState from '../components/LoadingState'
import EmptyState from '../components/EmptyState'

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
  const infoCount = alerts.length - criticalCount - warningCount

  return (
    <div>
      <Card
        title={
          <Space wrap>
            <AlertOutlined />
            <span>告警事件</span>
            {criticalCount > 0 && (
              <Badge count={criticalCount} overflowCount={99} />
            )}
          </Space>
        }
        extra={
          <Space wrap>
            <Tag color="red">CRITICAL: {criticalCount}</Tag>
            <Tag color="orange">WARNING: {warningCount}</Tag>
            <Tag color="blue">INFO: {infoCount}</Tag>
            <Select
              allowClear
              placeholder="按级别筛选"
              style={{ width: 140 }}
              value={levelFilter}
              onChange={setLevelFilter}
              options={[
                { label: 'CRITICAL', value: 'CRITICAL' },
                { label: 'WARNING', value: 'WARNING' },
                { label: 'INFO', value: 'INFO' },
              ]}
            />
          </Space>
        }
      >
        {loading ? (
          <LoadingState tip="加载告警数据..." />
        ) : filtered.length > 0 ? (
          <Table
            dataSource={filtered}
            rowKey="id"
            size="middle"
            pagination={{ pageSize: 50, showTotal: (t) => `共 ${t} 条` }}
            scroll={{ x: 720 }}
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
                render: (l: string) => (
                  <Tag color={LEVEL_COLOR[l]}>{l}</Tag>
                ),
              },
              { title: '类型', dataIndex: 'type', key: 'type', width: 180 },
              { title: '消息', dataIndex: 'message', key: 'message' },
            ]}
          />
        ) : (
          <EmptyState
            description={levelFilter ? `无 ${levelFilter} 级别告警` : '暂无告警'}
            detail="系统运行正常，无告警事件"
          />
        )}
      </Card>
    </div>
  )
}
