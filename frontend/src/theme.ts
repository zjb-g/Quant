import type { ThemeConfig } from 'antd'
import { theme } from 'antd'
import { palette, spacing, radius, fonts } from './theme/tokens'

export type ThemeMode = 'dark' | 'light'

const shared = {
  token: {
    colorPrimary: palette.primary,
    colorSuccess: palette.profit,
    colorError: palette.loss,
    colorWarning: palette.warning,
    colorInfo: palette.primary,
    borderRadius: radius.lg,
    borderRadiusLG: radius.xl,
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontSize: 14,
    controlHeight: 38,
    paddingXS: spacing.xs,
    paddingSM: spacing.sm,
    paddingMD: spacing.md,
    paddingLG: spacing.lg,
    paddingXL: spacing.xl,
    marginXS: spacing.xs,
    marginSM: spacing.sm,
    marginMD: spacing.md,
    marginLG: spacing.lg,
    marginXL: spacing.xl,
    marginXXL: spacing.xxl,
    lineHeight: 1.5715,
    wireframe: false,
  },
  components: {
    Layout: {
      siderBg: 'transparent',
      headerBg: 'transparent',
      bodyBg: 'transparent',
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedColor: palette.primary,
      itemBorderRadius: radius.md,
      iconSize: 16,
      itemMarginInline: 4,
    },
    Button: {
      primaryShadow: `0 4px 14px ${palette.primary}33`,
      borderRadius: radius.md,
      controlHeight: 38,
      paddingContentHorizontal: 16,
    },
    Card: {
      borderRadiusLG: radius.xl,
      paddingLG: spacing.xl,
    },
    Table: {
      borderRadiusLG: radius.lg,
      cellFontSize: 13,
      cellPaddingBlock: 10,
      cellPaddingInline: 12,
    },
    Statistic: {
      contentFontSize: 28,
      titleFontSize: 13,
    },
    Input: {
      borderRadius: radius.md,
      controlHeight: 38,
    },
    Select: {
      borderRadius: radius.md,
      controlHeight: 38,
    },
    Tag: {
      borderRadiusSM: radius.sm,
    },
    Modal: {
      borderRadiusLG: radius.xl,
    },
    Breadcrumb: {
      fontSize: 13,
    },
  },
} as const satisfies ThemeConfig

export function createAppTheme(mode: ThemeMode): ThemeConfig {
  if (mode === 'light') {
    return {
      algorithm: theme.defaultAlgorithm,
      token: {
        ...shared.token,
        colorBgBase: '#f5f7fa',
        colorBgContainer: '#ffffff',
        colorBgElevated: '#ffffff',
        colorBgLayout: '#f0f2f5',
        colorBorder: 'rgba(0, 0, 0, 0.08)',
        colorBorderSecondary: 'rgba(0, 0, 0, 0.04)',
        colorText: '#1a1a2e',
        colorTextSecondary: '#525252',
        colorTextTertiary: '#a3a3a3',
        colorTextQuaternary: '#d4d4d4',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
        boxShadowSecondary: '0 2px 8px rgba(0, 0, 0, 0.04)',
        colorFillAlter: '#fafafa',
        colorFillContent: 'rgba(0, 0, 0, 0.04)',
        colorFillContentHover: 'rgba(0, 0, 0, 0.08)',
      },
      components: {
        ...shared.components,
        Menu: {
          ...shared.components!.Menu,
          itemSelectedBg: `${palette.primary}15`,
          itemHoverBg: 'rgba(0, 0, 0, 0.03)',
          subMenuItemBg: 'transparent',
        },
        Card: {
          ...shared.components!.Card,
          colorBgContainer: '#ffffff',
        },
        Table: {
          ...shared.components!.Table,
          headerBg: '#fafafa',
          headerColor: '#525252',
          rowHoverBg: `${palette.primary}08`,
          borderColor: 'rgba(0, 0, 0, 0.06)',
        },
        Tag: {
          defaultBg: 'rgba(0, 0, 0, 0.04)',
        },
        Drawer: {
          colorBgElevated: '#ffffff',
        },
        Segmented: {
          itemSelectedBg: '#ffffff',
        },
      },
    }
  }

  // Dark mode
  return {
    algorithm: theme.darkAlgorithm,
    token: {
      ...shared.token,
      colorPrimary: '#4096ff',
      colorSuccess: '#73d13d',
      colorError: '#ff7875',
      colorWarning: '#ffc53d',
      colorInfo: '#4096ff',
      colorBgBase: '#0a0e18',
      colorBgContainer: '#111827',
      colorBgElevated: '#1a2234',
      colorBgLayout: '#080c14',
      colorBorder: 'rgba(148, 163, 184, 0.14)',
      colorBorderSecondary: 'rgba(148, 163, 184, 0.08)',
      colorText: '#e2e8f0',
      colorTextSecondary: '#94a3b8',
      colorTextTertiary: '#64748b',
      colorTextQuaternary: '#334155',
      boxShadow: '0 4px 24px rgba(0, 0, 0, 0.25)',
      boxShadowSecondary: '0 2px 12px rgba(0, 0, 0, 0.2)',
      colorFillAlter: 'rgba(255, 255, 255, 0.04)',
      colorFillContent: 'rgba(255, 255, 255, 0.06)',
      colorFillContentHover: 'rgba(255, 255, 255, 0.1)',
    },
    components: {
      ...shared.components,
      Menu: {
        ...shared.components!.Menu,
        itemSelectedBg: `${palette.primary}1f`,
        itemSelectedColor: '#4096ff',
        itemHoverBg: 'rgba(148, 163, 184, 0.08)',
        subMenuItemBg: 'transparent',
      },
      Card: {
        ...shared.components!.Card,
        colorBgContainer: 'rgba(17, 24, 39, 0.72)',
        colorBorderSecondary: 'rgba(148, 163, 184, 0.12)',
      },
      Table: {
        ...shared.components!.Table,
        headerBg: 'rgba(15, 23, 42, 0.6)',
        headerColor: '#94a3b8',
        rowHoverBg: `${palette.primary}10`,
        borderColor: 'rgba(148, 163, 184, 0.08)',
      },
      Tag: {
        defaultBg: 'rgba(148, 163, 184, 0.12)',
      },
      Drawer: {
        colorBgElevated: '#0f172a',
      },
      Segmented: {
        itemSelectedBg: '#1a2234',
      },
    },
  }
}

export { palette, spacing, radius, fonts }
export { pnlColor, pnlBg, numAlign } from './theme/tokens'
