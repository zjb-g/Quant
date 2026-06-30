import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Alert, Button, Card, Form, Input, Typography, message } from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { apiClient, clearAuthToken, setAuthToken } from '../api/client'

export default function LoginPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(true)
  const [allowRegister, setAllowRegister] = useState(false)

  useEffect(() => {
    apiClient.authStatus()
      .then((status) => {
        if (!status.enabled) {
          navigate('/dashboard', { replace: true })
          return
        }
        setAllowRegister(status.allow_register ?? false)
        if (status.authenticated) {
          navigate('/dashboard', { replace: true })
        }
      })
      .catch(() => setAllowRegister(false))
      .finally(() => setChecking(false))
  }, [navigate])

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const result = await apiClient.login(values.username, values.password)
      setAuthToken(result.access_token)
      navigate('/dashboard', { replace: true })
    } catch {
      clearAuthToken()
      message.error('用户名或密码错误')
    } finally {
      setLoading(false)
    }
  }

  if (checking) {
    return null
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px 16px',
        boxSizing: 'border-box',
        background: 'linear-gradient(160deg, #0f1419 0%, #1a2332 50%, #0d1117 100%)',
      }}
    >
      <Card style={{ width: 400, maxWidth: '100%' }}>
        <Typography.Title level={3} style={{ marginTop: 0, textAlign: 'center' }}>
          量化控制台登录
        </Typography.Title>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="登录后可使用自己的账号；新用户请先注册，再导入 OKX API Key。"
        />
        <Form layout="vertical" onFinish={onFinish} autoComplete="off">
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="WEB_AUTH_USERNAME" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="WEB_AUTH_PASSWORD" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            登录
          </Button>
        {allowRegister && (
          <div style={{ marginTop: 12, textAlign: 'center' }}>
            <Link to="/register">没有账号？立即注册</Link>
          </div>
        )}
        </Form>
      </Card>
    </div>
  )
}
