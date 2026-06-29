import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import DashboardPage from './pages/DashboardPage'
import BacktestPage from './pages/BacktestPage'
import ControlPage from './pages/ControlPage'
import AlertsPage from './pages/AlertsPage'
import StrategyPage from './pages/StrategyPage'
import ExchangePage from './pages/ExchangePage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="backtest" element={<BacktestPage />} />
        <Route path="strategy" element={<StrategyPage />} />
        <Route path="exchange" element={<ExchangePage />} />
        <Route path="control" element={<ControlPage />} />
        <Route path="alerts" element={<AlertsPage />} />
      </Route>
    </Routes>
  )
}
