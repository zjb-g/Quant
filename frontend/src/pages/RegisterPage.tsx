import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Alert, Button, Card, Form, Input, Typography, message, Divider } from 'antd'
import { LockOutlined, UserOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { apiClient, clearAuthToken, setAuthToken } from '../api/client'
import ThemeToggle from '../components/ThemeToggle'

const { Title, Text } = Typography

export default function RegisterPage() {
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
        if (status.authenticated) {
          navigate('/dashboard', { replace: true })
          return
        }
        setAllowRegister(status.allow_register ?? false)
      })
      .catch(() => setAllowRegister(false))
      .finally(() => setChecking(false))
  }, [navigate])

  const onFinish = async (values: { username: string; password: string; confirm: string }) => {
    if (values.password !== values.confirm) {
      message.warning('两次输入的密码不一致')
      return
    }
    setLoading(true)
    try {
      const result = await apiClient.register(values.username, values.password)
      setAuthToken(result.access_token)
      message.success('注册成功，请前往「交易所连接」导入 API Key')
      navigate('/exchange', { replace: true })
    } catch (err: unknown) {
      clearAuthToken()
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail || '注册失败')
    } finally {
      setLoading(false)
    }
  }

  if (checking) {
    return null
  }

  if (!allowRegister) {
    return (
      <div className="auth-page">
        <div className="auth-bg-decoration" />
        <div className="auth-page-toggle">
          <ThemeToggle />
        </div>
        <Card className="auth-card" bordered={false}>
          <div className="auth-logo">
            <div className="auth-logo-mark">
              <ThunderboltOutlined style={{ fontSize: 24 }} />
            </div>
            <Title level={2} className="auth-title">
              Crypto Quant
            </Title>
          </div>
          <Alert
            type="warning"
            message="当前未开放注册"
            description="请联系管理员获取账号。"
            showIcon
          />
          <div style={{ marginTop: 16, textAlign: 'center' }}>
            <Link to="/login" className="auth-link">返回登录</Link>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="auth-page">
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
            创建您的量化交易账号
          </Text>
        </div>

        <Divider style={{ margin: '0 0 20px' }} />

        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
          message="注册后可保存自己的 OKX API Key，独立查看持仓复盘数据。"
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
            rules={[
              { required: true, message: '请输入用户名' },
              { pattern: /^[A-Za-z0-9_]{3,32}$/, message: '3-32 位字母、数字或下划线' },
            ]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="例如 trader01"
            />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, message: '至少 8 位' },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="至少 8 位密码"
            />
          </Form.Item>

          <Form.Item
            name="confirm"
            label="确认密码"
            rules={[{ required: true, message: '请再次输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="再次输入密码"
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
            注册并登录
          </Button>

          <div style={{ marginTop: 20, textAlign: 'center' }}>
            <Text type="secondary">已有账号？</Text>{' '}
            <Link to="/login" className="auth-link">
              去登录
            </Link>
          </div>
        </Form>
      </Card>
    </div>
  )
}
