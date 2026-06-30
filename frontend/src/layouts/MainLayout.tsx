import { useState, useEffect } from 'react'
import { Layout, Menu, Badge, Button, Drawer, theme } from 'antd'
import {
  DashboardOutlined,
  LineChartOutlined,
  ControlOutlined,
  AlertOutlined,
  CodeOutlined,
  ApiOutlined,
  FundOutlined,
  BarChartOutlined,
  LogoutOutlined,
  MenuOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { apiClient, clearAuthToken } from '../api/client'
import { useIsMobile } from '../hooks/useIsMobile'

const { Header, Sider, Content } = Layout

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [alertCount, setAlertCount] = useState(0)
  const [authEnabled, setAuthEnabled] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { token } = theme.useToken()
  const isMobile = useIsMobile()

  useEffect(() => {
    apiClient.authStatus().then((s) => setAuthEnabled(s.enabled)).catch(() => {})
  }, [])

  useEffect(() => {
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

  useEffect(() => {
    setDrawerOpen(false)
  }, [location.pathname])

  const menuItems = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: '/backtest', icon: <LineChartOutlined />, label: '回测分析' },
    { key: '/strategy', icon: <CodeOutlined />, label: '策略管理' },
    { key: '/exchange', icon: <ApiOutlined />, label: '交易所连接' },
    { key: '/review', icon: <FundOutlined />, label: '持仓复盘' },
    { key: '/analysis', icon: <BarChartOutlined />, label: '持仓分析' },
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

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
    if (isMobile) setDrawerOpen(false)
  }

  const menu = (
    <Menu
      mode="inline"
      selectedKeys={[location.pathname]}
      items={menuItems}
      onClick={handleMenuClick}
    />
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {!isMobile && (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          style={{ background: token.colorBgContainer }}
          breakpoint="lg"
          collapsedWidth={64}
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
          {menu}
        </Sider>
      )}
      <Layout>
        <Header
          className="app-header"
          style={{
            padding: isMobile ? '0 12px' : '0 24px',
            background: token.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            lineHeight: 'normal',
            height: isMobile ? 52 : 64,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
            {isMobile && (
              <Button
                type="text"
                icon={<MenuOutlined />}
                onClick={() => setDrawerOpen(true)}
                aria-label="打开菜单"
              />
            )}
            <span
              className="app-header-title"
              style={{
                fontSize: isMobile ? 15 : 16,
                fontWeight: 600,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {isMobile ? 'Crypto Quant' : '个人加密永续合约量化交易系统'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 4 : 16, flexShrink: 0 }}>
            {!isMobile && (
              <span style={{ color: token.colorTextSecondary, fontSize: 13 }}>
                OKX · USDT 永续 · 15m · 5x
              </span>
            )}
            {authEnabled && (
              <Button
                type="text"
                icon={<LogoutOutlined />}
                onClick={() => {
                  clearAuthToken()
                  navigate('/login')
                }}
              >
                {isMobile ? '' : '退出登录'}
              </Button>
            )}
          </div>
        </Header>
        <Content
          className="app-content"
          style={{
            margin: isMobile ? 8 : 16,
            padding: isMobile ? 12 : 24,
            background: token.colorBgContainer,
            borderRadius: 8,
          }}
        >
          <Outlet />
        </Content>
      </Layout>
      {isMobile && (
        <Drawer
          title="Crypto Quant"
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={280}
          styles={{ body: { padding: 0 } }}
        >
          {menu}
        </Drawer>
      )}
    </Layout>
  )
}
