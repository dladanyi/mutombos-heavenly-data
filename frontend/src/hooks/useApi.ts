import { useCallback, useEffect, useRef, useState } from 'react'
import type { ApiError } from '../api'

export type ApiState<T> = {
  data: T | undefined
  error: ApiError | Error | undefined
  loading: boolean
  refreshing: boolean
  reload: (refresh?: boolean) => Promise<void>
}

/** Loads data on mount and whenever `deps` change; `reload(true)` asks the API to skip its cache. */
export function useApi<T>(load: (refresh: boolean) => Promise<T>, deps: unknown[]): ApiState<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<ApiError | Error>()
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const loadRef = useRef(load)
  loadRef.current = load
  const requestId = useRef(0)

  const run = useCallback(async (refresh: boolean) => {
    const id = ++requestId.current
    if (refresh) setRefreshing(true)
    else setLoading(true)
    try {
      const result = await loadRef.current(refresh)
      if (id !== requestId.current) return
      setData(result)
      setError(undefined)
    } catch (e) {
      if (id !== requestId.current) return
      setError(e instanceof Error ? e : new Error(String(e)))
    } finally {
      if (id === requestId.current) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  useEffect(() => {
    // Data from the previous deps (e.g. last week's table) must not show under the new title.
    setData(undefined)
    setError(undefined)
    void run(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  const reload = useCallback((refresh = false) => run(refresh), [run])
  return { data, error, loading, refreshing, reload }
}
