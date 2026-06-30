import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import MainLayout from './layouts/MainLayout'
import DashboardPage from './pages/DashboardPage'
import BacktestPage from './pages/BacktestPage'
import ControlPage from './pages/ControlPage'
import AlertsPage from './pages/AlertsPage'
import StrategyPage from './pages/StrategyPage'
import ExchangePage from './pages/ExchangePage'

// 持仓复盘页含 lightweight-charts，按需懒加载，避免拖慢首页
const TradeReviewPage = lazy(() => import('./pages/TradeReviewPage'))
const TradeAnalysisPage = lazy(() => import('./pages/TradeAnalysisPage'))

function PageLoader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
      <Spin size="large" tip="页面加载中..." />
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="backtest" element={<BacktestPage />} />
        <Route path="strategy" element={<StrategyPage />} />
        <Route path="exchange" element={<ExchangePage />} />
        <Route path="review" element={
          <Suspense fallback={<PageLoader />}>
            <TradeReviewPage />
          </Suspense>
        } />
        <Route path="analysis" element={
          <Suspense fallback={<PageLoader />}>
            <TradeAnalysisPage />
          </Suspense>
        } />
        <Route path="control" element={<ControlPage />} />
        <Route path="alerts" element={<AlertsPage />} />
      </Route>
    </Routes>
  )
}
