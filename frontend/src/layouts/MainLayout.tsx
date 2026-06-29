import { useState, useEffect } from 'react'
import { Layout, Menu, Badge, theme } from 'antd'
import {
  DashboardOutlined,
  LineChartOutlined,
  ControlOutlined,
  AlertOutlined,
  CodeOutlined,
  ApiOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'

const { Header, Sider, Content } = Layout

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [alertCount, setAlertCount] = useState(0)
  const location = useLocation()
  const navigate = useNavigate()
  const { token } = theme.useToken()

  useEffect(() => {
    // 轮询未读告警数
    const fetchAlerts = () => {
      apiClient.getAlerts(10).then((alerts) => {
        const critical = alerts.filter((a) => a.level === 'CRITICAL').length
        setAlertCount(critical)
      }).catch(() => {})
    }
    fetchAlerts()
    const timer = setInterval(fetchAlerts, 30000)
    return () => clearInterval(timer)
  }, [])

  const menuItems = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: '/backtest', icon: <LineChartOutlined />, label: '回测分析' },
    { key: '/strategy', icon: <CodeOutlined />, label: '策略管理' },
    { key: '/exchange', icon: <ApiOutlined />, label: '交易所连接' },
    { key: '/control', icon: <ControlOutlined />, label: '控制台' },
    {
      key: '/alerts',
      icon: (
        <Badge count={alertCount} size="small" offset={[6, 0]}>
          <AlertOutlined />
        </Badge>
      ),
      label: '告警',
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{ background: token.colorBgContainer }}
      >
        <div
          style={{
            height: 48,
            margin: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: token.colorPrimary,
            fontWeight: 700,
            fontSize: collapsed ? 14 : 16,
          }}
        >
          {collapsed ? 'Q' : 'Crypto Quant'}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 24px',
            background: token.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontSize: 16, fontWeight: 600 }}>
            个人加密永续合约量化交易系统
          </span>
          <span style={{ color: token.colorTextSecondary, fontSize: 13 }}>
            OKX · USDT 永续 · 15m · 5x
          </span>
        </Header>
        <Content style={{ margin: 16, padding: 24, background: token.colorBgContainer, borderRadius: 8 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
