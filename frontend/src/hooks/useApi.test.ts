import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useApi } from './useApi'

describe('useApi', () => {
  it('drops data from old deps while new deps load', async () => {
    let resolveSecond: (value: string) => void = () => {}
    const load = (week: number) => () =>
      week === 6 ? Promise.resolve('week 6') : new Promise<string>((resolve) => (resolveSecond = resolve))
    const { result, rerender } = renderHook(({ week }) => useApi(load(week), [week]), {
      initialProps: { week: 6 },
    })
    await waitFor(() => expect(result.current.data).toBe('week 6'))

    rerender({ week: 7 })
    expect(result.current.data).toBeUndefined()
    expect(result.current.loading).toBe(true)

    await act(async () => resolveSecond('week 7'))
    expect(result.current.data).toBe('week 7')
  })

  it('keeps data during a refresh of the same deps', async () => {
    const { result } = renderHook(() => useApi(() => Promise.resolve('x'), []))
    await waitFor(() => expect(result.current.data).toBe('x'))
    act(() => void result.current.reload(true))
    expect(result.current.data).toBe('x')
    await waitFor(() => expect(result.current.refreshing).toBe(false))
  })
})
