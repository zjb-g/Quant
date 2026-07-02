import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Alert, Button, Card, Form, Input, Typography, message, Divider } from 'antd'
import { LockOutlined, UserOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { apiClient, clearAuthToken, setAuthToken } from '../api/client'
import ThemeToggle from '../components/ThemeToggle'

const { Title, Text } = Typography

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
    <div className="auth-page">
      {/* 背景装饰 */}
      <div className="auth-bg-decoration" />

      <div className="auth-page-toggle">
        <ThemeToggle />
      </div>

      <Card className="auth-card" bordered={false}>
        {/* 品牌标识 */}
        <div className="auth-logo">
          <div className="auth-logo-mark">
            <ThunderboltOutlined style={{ fontSize: 24 }} />
          </div>
          <Title level={2} className="auth-title">
            Crypto Quant
          </Title>
          <Text type="secondary" style={{ fontSize: 13, textAlign: 'center' }}>
            个人加密永续合约量化交易系统
          </Text>
        </div>

        <Divider style={{ margin: '0 0 20px' }} />

        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
          message="登录后可使用自己的账号；新用户请先注册，再导入 OKX API Key。"
        />

        <Form
          layout="vertical"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="请输入用户名"
            />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="请输入密码"
            />
          </Form.Item>

          <Button
            type="primary"
            htmlType="submit"
            block
            loading={loading}
            size="large"
            style={{ height: 44, fontWeight: 600 }}
          >
            登录控制台
          </Button>

          {allowRegister && (
            <div style={{ marginTop: 20, textAlign: 'center' }}>
              <Text type="secondary">还没有账号？</Text>{' '}
              <Link to="/register" className="auth-link">
                立即注册
              </Link>
            </div>
          )}
        </Form>
      </Card>
    </div>
  )
}
