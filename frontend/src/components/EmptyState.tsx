import { Empty as AntEmpty, Button, type EmptyProps } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'

interface Props extends EmptyProps {
  /** 空状态的主描述 */
  description?: string
  /** 副描述（更详细的说明） */
  detail?: string
  /** 重试回调 */
  onRetry?: () => void
  /** 操作区自定义内容 */
  action?: React.ReactNode
}

/**
 * 统一空状态组件
 * 用于列表/图表无数据时的占位展示
 */
export default function EmptyState({
  description = '暂无数据',
  detail,
  onRetry,
  action,
  style,
  ...rest
}: Props) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: 220,
        flexDirection: 'column',
        gap: 8,
        ...style,
      }}
    >
      <AntEmpty
        description={description}
        style={{ margin: 0 }}
        {...rest}
      />
      {detail && (
        <div
          style={{
            color: 'var(--app-text-muted)',
            fontSize: 13,
            textAlign: 'center',
            maxWidth: 320,
            marginTop: -4,
          }}
        >
          {detail}
        </div>
      )}
      {onRetry && !action && (
        <Button
          icon={<ReloadOutlined />}
          onClick={onRetry}
          style={{ marginTop: 4 }}
        >
          重新加载
        </Button>
      )}
      {action}
    </div>
  )
}
