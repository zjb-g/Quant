import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { createAppTheme, type ThemeMode } from '../theme'

const STORAGE_KEY = 'quant_theme_mode'

type ThemeContextValue = {
  mode: ThemeMode
  toggleTheme: () => void
  isDark: boolean
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function readStoredMode(): ThemeMode {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'light' || v === 'dark') return v
  } catch {
    /* ignore */
  }
  return 'dark'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(readStoredMode)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', mode)
    try {
      localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      /* ignore */
    }
  }, [mode])

  const value = useMemo<ThemeContextValue>(
    () => ({
      mode,
      isDark: mode === 'dark',
      toggleTheme: () => setMode((m) => (m === 'dark' ? 'light' : 'dark')),
    }),
    [mode],
  )

  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider locale={zhCN} theme={createAppTheme(mode)}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  )
}

export function useThemeMode() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useThemeMode must be used within ThemeProvider')
  return ctx
}
