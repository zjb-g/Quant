import { Button, Tooltip } from 'antd'
import { MoonOutlined, SunOutlined } from '@ant-design/icons'
import { useThemeMode } from '../context/ThemeContext'

type Props = {
  className?: string
  size?: 'small' | 'middle' | 'large'
}

export default function ThemeToggle({ className, size = 'middle' }: Props) {
  const { isDark, toggleTheme } = useThemeMode()

  return (
    <Tooltip title={isDark ? '切换浅色模式' : '切换深色模式'}>
      <Button
        className={className}
        type="text"
        size={size}
        aria-label={isDark ? '切换浅色模式' : '切换深色模式'}
        icon={isDark ? <SunOutlined /> : <MoonOutlined />}
        onClick={toggleTheme}
        style={{ color: 'var(--app-text-muted)' }}
      />
    </Tooltip>
  )
}
