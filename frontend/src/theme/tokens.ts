/**
 * 设计令牌（Design Tokens）
 * 统一管理色板/间距/圆角/字体等基础设计变量
 */

// ─── 色板 ────────────────────────────────────────────
export const palette = {
  primary: '#1677ff',
  primaryHover: '#4096ff',
  primaryActive: '#0958d9',

  profit: '#52c41a',
  profitBg: 'rgba(82, 196, 26, 0.1)',
  profitBorder: 'rgba(82, 196, 26, 0.35)',

  loss: '#ff4d4f',
  lossBg: 'rgba(255, 77, 79, 0.1)',
  lossBorder: 'rgba(255, 77, 79, 0.35)',

  warning: '#faad14',
  warningBg: 'rgba(250, 173, 20, 0.1)',

  link: '#1677ff',

  // Neutral
  neutral: {
    50: '#fafafa',
    100: '#f5f5f5',
    200: '#e5e5e5',
    300: '#d4d4d4',
    400: '#a3a3a3',
    500: '#737373',
    600: '#525252',
    700: '#404040',
    800: '#262626',
    900: '#171717',
  },
} as const

// ─── 间距 ────────────────────────────────────────────
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const

// ─── 圆角 ────────────────────────────────────────────
export const radius = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
} as const

// ─── 阴影 ────────────────────────────────────────────
export const shadows = {
  card: '0 2px 8px rgba(0, 0, 0, 0.06)',
  cardHover: '0 6px 20px rgba(0, 0, 0, 0.1)',
  dropdown: '0 6px 16px rgba(0, 0, 0, 0.08)',
  modal: '0 12px 48px rgba(0, 0, 0, 0.15)',
} as const

// ─── 字体 ────────────────────────────────────────────
export const fonts = {
  mono: "'SF Mono', 'Consolas', 'Monaco', 'Courier New', monospace",
  number: "'Inter', 'SF Mono', 'Tabular Numbers', monospace",
} as const

// ─── 动画 ────────────────────────────────────────────
export const motion = {
  fast: '0.15s ease',
  normal: '0.25s ease',
  slow: '0.4s ease',
} as const

// ─── 表格列辅助 ──────────────────────────────────────
/** Table 列数字右对齐（仅 align，不包含 CSS 属性避免类型冲突） */
export const numAlign = { align: 'right' as const }

// ─── 盈亏颜色辅助 ──────────────────────────────────────
export function pnlColor(value: number): string {
  return value >= 0 ? palette.profit : palette.loss
}

export function pnlBg(value: number): string {
  return value >= 0 ? palette.profitBg : palette.lossBg
}
