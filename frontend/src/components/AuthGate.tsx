import { useEffect, useState, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import { apiClient } from '../api/client'

export default function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<'loading' | 'ok' | 'login'>('loading')

  useEffect(() => {
    apiClient.authStatus()
      .then((status) => {
        if (!status.enabled || status.authenticated) {
          setState('ok')
        } else {
          setState('login')
        }
      })
      .catch(() => setState('login'))
  }, [])

  if (state === 'loading') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 120 }}>
        <Spin size="large" tip="验证登录状态..." />
      </div>
    )
  }

  if (state === 'login') {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
