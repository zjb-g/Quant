import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Alert, Button, Card, Form, Input, Typography, message } from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { apiClient, clearAuthToken, setAuthToken } from '../api/client'

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
        setAllowRegister(status.allow_register)
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
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <Card style={{ width: 400, maxWidth: '100%' }}>
          <Alert type="warning" message="当前未开放注册" description="请联系管理员获取账号。" />
          <Button type="link" style={{ marginTop: 12, padding: 0 }}>
            <Link to="/login">返回登录</Link>
          </Button>
        </Card>
      </div>
    )
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
          注册账号
        </Typography.Title>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="注册后可保存自己的 OKX API Key，独立查看持仓复盘数据。"
        />
        <Form layout="vertical" onFinish={onFinish} autoComplete="off">
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { pattern: /^[A-Za-z0-9_]{3,32}$/, message: '3-32 位字母、数字或下划线' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="例如 trader01" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, message: '至少 8 位' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="至少 8 位" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认密码"
            rules={[{ required: true, message: '请再次输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="再次输入密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            注册并登录
          </Button>
          <div style={{ marginTop: 12, textAlign: 'center' }}>
            <Link to="/login">已有账号？去登录</Link>
          </div>
        </Form>
      </Card>
    </div>
  )
}
