import { useCallback, useEffect, useState } from 'react'
import { apiClient, type StrategyInfo } from '../api/client'

function formatStrategyLabel(s: StrategyInfo): string {
  const stem = s.filename.replace(/\.py$/i, '')
  if (stem !== s.name) {
    return `${s.name}（${s.filename}）`
  }
  return s.name
}

export function useStrategies(preferredName = 'EmaCrossoverStrategy') {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [selected, setSelected] = useState(preferredName)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    setLoading(true)
    setError(null)
    return apiClient.getStrategies()
      .then((list) => {
        setStrategies(list)
        const pick =
          list.find((s) => s.name === preferredName && !s.has_errors)
          ?? list.find((s) => !s.has_errors)
          ?? list[0]
        if (pick) {
          setSelected(pick.name)
        }
        return list
      })
      .catch((err: unknown) => {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        setError(detail || '加载策略列表失败')
        return [] as StrategyInfo[]
      })
      .finally(() => setLoading(false))
  }, [preferredName])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const options = strategies.map((s) => ({
    value: s.name,
    label: formatStrategyLabel(s),
    disabled: s.has_errors,
    title: s.has_errors ? s.error_msg || '策略有语法错误' : s.description,
  }))

  const runnableCount = strategies.filter((s) => !s.has_errors).length

  return {
    strategies,
    selected,
    setSelected,
    loading,
    error,
    options,
    refresh,
    runnableCount,
  }
}
