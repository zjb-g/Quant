import { Alert, Button, Space, type AlertProps } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'

interface Props {
  /** 错误消息 */
  message?: string
  /** 详细错误描述 */
  description?: string
  /** 重试回调 */
  onRetry?: () => void
  /** 自定义操作区 */
  action?: React.ReactNode
  /** 是否占满容器 */
  fullPage?: boolean
  /** Alert 的 type */
  type?: AlertProps['type']
}

/**
 * 统一错误状态组件
 * 用于 API 请求失败等异常场景
 */
export default function ErrorState({
  message = '加载失败',
  description,
  onRetry,
  action,
  fullPage = false,
  type = 'error',
}: Props) {
  const content = (
    <div style={{ maxWidth: 560, width: '100%' }}>
      <Alert
        type={type}
        showIcon
        message={message}
        description={
          description ? (
            <pre style={{
              margin: '6px 0 0',
              whiteSpace: 'pre-wrap',
              fontSize: 12,
              fontFamily: 'var(--app-font-mono, monospace)',
              color: 'var(--app-text-muted)',
            }}>
              {description}
            </pre>
          ) : undefined
        }
        action={
          (onRetry || action) ? (
            <Space>
              {onRetry && (
                <Button
                  size="small"
                  icon={<ReloadOutlined />}
                  onClick={onRetry}
                  danger={type === 'error'}
                >
                  重试
                </Button>
              )}
              {action}
            </Space>
          ) : undefined
        }
      />
    </div>
  )

  if (fullPage) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: 320,
          padding: 24,
        }}
      >
        {content}
      </div>
    )
  }

  return <div style={{ marginBottom: 16 }}>{content}</div>
}
