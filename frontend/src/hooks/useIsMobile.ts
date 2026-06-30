import { Grid } from 'antd'

/** 屏幕宽度 < 768px（antd md 断点）视为手机/窄屏 */
export function useIsMobile(): boolean {
  const screens = Grid.useBreakpoint()
  return !screens.md
}
