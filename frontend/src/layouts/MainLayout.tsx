import { useState, useEffect, useMemo } from 'react'
import { Layout, Menu, Badge, Button, Drawer, Tag, Breadcrumb } from 'antd'
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
import { Outlet, useLocation, useNavigate, Link } from 'react-router-dom'
import { apiClient, clearAuthToken } from '../api/client'
import ThemeToggle from '../components/ThemeToggle'
import { useIsMobile } from '../hooks/useIsMobile'
import type { MenuProps } from 'antd'

const { Header, Sider, Content } = Layout

type MenuItem = Required<MenuProps>['items'][number]

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': '仪表盘',
  '/backtest': '回测分析',
  '/strategy': '策略管理',
  '/exchange': '交易所连接',
  '/review': '持仓复盘',
  '/analysis': '持仓分析',
  '/control': '控制台',
  '/alerts': '告警中心',
}

const BREADCRUMB_NAMES: Record<string, string> = {
  '/dashboard': '仪表盘',
  '/backtest': '回测分析',
  '/strategy': '策略管理',
  '/exchange': '交易所连接',
  '/review': '持仓复盘',
  '/analysis': '持仓分析',
  '/control': '控制台',
  '/alerts': '告警中心',
}

function buildBreadcrumbs(pathname: string): { title: React.ReactNode; path: string }[] {
  const items = [{ title: '首页', path: '/dashboard' }]
  if (pathname === '/dashboard') return items
  const name = BREADCRUMB_NAMES[pathname]
  if (name) items.push({ title: name, path: pathname })
  return items
}

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [alertCount, setAlertCount] = useState(0)
  const [authEnabled, setAuthEnabled] = useState(false)
  const [okxConnected, setOkxConnected] = useState<boolean | null>(null)
  const location = useLocation()
  const navigate = useNavigate()
  const isMobile = useIsMobile()

  const pageTitle = PAGE_TITLES[location.pathname] ?? '量化系统'
  const breadcrumbs = buildBreadcrumbs(location.pathname)

  useEffect(() => {
    apiClient.authStatus().then((s) => setAuthEnabled(s.enabled)).catch(() => {})
  }, [])

  useEffect(() => {
    const checkOkx = () => {
      apiClient.getExchangeStatus()
        .then((s) => setOkxConnected(s.connected))
        .catch(() => setOkxConnected(false))
    }
    checkOkx()
    const timer = setInterval(checkOkx, 30000)
    return () => clearInterval(timer)
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

  const menuItems: MenuItem[] = useMemo(() => [
    {
      type: 'group',
      label: '交易类',
      key: 'group-trading',
      children: [
        { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
        { key: '/exchange', icon: <ApiOutlined />, label: '交易所连接' },
        { key: '/review', icon: <FundOutlined />, label: '持仓复盘' },
        { key: '/analysis', icon: <BarChartOutlined />, label: '持仓分析' },
      ],
    },
    {
      type: 'group',
      label: '策略类',
      key: 'group-strategy',
      children: [
        { key: '/strategy', icon: <CodeOutlined />, label: '策略管理' },
        { key: '/backtest', icon: <LineChartOutlined />, label: '回测分析' },
      ],
    },
    {
      type: 'group',
      label: '系统类',
      key: 'group-system',
      children: [
        { key: '/control', icon: <ControlOutlined />, label: '控制台' },
        {
          key: '/alerts',
          icon: (
            <Badge count={alertCount} size="small" offset={[6, 0]}>
              <AlertOutlined />
            </Badge>
          ),
          label: '告警中心',
        },
      ],
    },
  ], [alertCount])

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    navigate(key)
    if (isMobile) setDrawerOpen(false)
  }

  const brand = (compact?: boolean) => (
    <div className={`app-brand${compact ? ' collapsed' : ''}`}>
      <div className="app-brand-mark">Q</div>
      {!compact && <span className="app-brand-text">Crypto Quant</span>}
    </div>
  )

  const menu = (
    <Menu
      mode="inline"
      selectedKeys={[location.pathname]}
      items={menuItems}
      onClick={handleMenuClick}
    />
  )

  const okxTag = (
    <Tag
      className="okx-tag"
      color={okxConnected === null ? 'default' : okxConnected ? 'success' : 'error'}
      style={{ margin: 0, fontSize: isMobile ? 12 : 13, borderRadius: 20, padding: '2px 10px' }}
    >
      {okxConnected === null ? '检测 OKX…' : okxConnected ? '已连接 OKX' : '未连接 OKX'}
    </Tag>
  )

  return (
    <Layout className="app-shell">
      {!isMobile && (
        <Sider
          className="app-sider"
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          breakpoint="lg"
          collapsedWidth={64}
          width={232}
        >
          {brand(collapsed)}
          {menu}
        </Sider>
      )}
      <Layout>
        <Header
          className="app-header"
          style={{
            padding: isMobile ? '0 12px' : '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            lineHeight: 'normal',
            height: isMobile ? 52 : 64,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
            {isMobile && (
              <Button
                type="text"
                icon={<MenuOutlined />}
                onClick={() => setDrawerOpen(true)}
                aria-label="打开菜单"
              />
            )}
            <div style={{ minWidth: 0 }}>
              <div className="app-header-title" style={{ fontSize: isMobile ? 16 : 18, fontWeight: 600 }}>
                {isMobile ? 'Crypto Quant' : pageTitle}
              </div>
              {!isMobile && (
                <div className="app-header-sub">个人加密永续合约量化交易系统</div>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 8 : 12, flexShrink: 0 }}>
            <ThemeToggle size={isMobile ? 'small' : 'middle'} />
            {okxTag}
            {authEnabled && (
              <Button
                type="text"
                icon={<LogoutOutlined />}
                onClick={() => {
                  clearAuthToken()
                  navigate('/login')
                }}
                style={{ color: 'var(--app-text-muted)' }}
              >
                {isMobile ? '' : '退出'}
              </Button>
            )}
          </div>
        </Header>

        {/* 面包屑 */}
        {!isMobile && (
          <div style={{ padding: '12px 24px 0' }}>
            <Breadcrumb
              items={breadcrumbs.map((item) => ({
                title: item.path === location.pathname
                  ? item.title
                  : <Link to={item.path} style={{ color: 'var(--app-text-muted)' }}>{item.title}</Link>,
              }))}
            />
          </div>
        )}

        <Content className="app-content" style={{ margin: isMobile ? 10 : 20, padding: 0 }}>
          <Outlet />
        </Content>
      </Layout>
      {isMobile && (
        <Drawer
          title={null}
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={260}
          className="app-sider"
          styles={{ body: { padding: '8px 0' } }}
        >
          {brand()}
          {menu}
        </Drawer>
      )}
    </Layout>
  )
}
