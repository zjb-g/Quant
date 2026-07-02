import { Spin, type SpinProps } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'

interface Props extends SpinProps {
  /** 加载提示文案 */
  tip?: string
  /** 占满容器 */
  fullPage?: boolean
}

/**
 * 统一加载状态组件
 * 用于各页面的数据加载等待场景
 */
export default function LoadingState({
  tip = '加载中...',
  fullPage = false,
  size = 'large',
  ...rest
}: Props) {
  const indicator = <LoadingOutlined spin />

  if (fullPage) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: 320,
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <Spin indicator={indicator} size={size} {...rest} />
        {tip && (
          <span style={{ color: 'var(--app-text-muted)', fontSize: 14 }}>
            {tip}
          </span>
        )}
      </div>
    )
  }

  return <Spin indicator={indicator} tip={tip} size={size} {...rest} />
}
