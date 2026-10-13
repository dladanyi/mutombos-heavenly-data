import { describe, expect, it, vi } from 'vitest'
import { ApiError, getLeague, getSeason, getWeek } from './api'

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockImplementation(async () =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('api', () => {
  it('getWeek builds the URL and refresh flag', async () => {
    const fetchMock = mockFetch(200, { scope: 'week' })
    await getWeek(7, { refresh: true })
    expect(fetchMock).toHaveBeenCalledWith('/api/rankings/week/7?refresh=1')
  })

  it("getWeek('current')", async () => {
    const fetchMock = mockFetch(200, { scope: 'week' })
    await getWeek('current')
    expect(fetchMock).toHaveBeenCalledWith('/api/rankings/week/current')
  })

  it('getLeague and getSeason use their endpoints', async () => {
    const fetchMock = mockFetch(200, {})
    await getLeague()
    await getSeason({ refresh: true })
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual(['/api/league', '/api/rankings/season?refresh=1'])
  })

  it('returns parsed JSON', async () => {
    mockFetch(200, { name: 'L', current_week: 3 })
    await expect(getLeague()).resolves.toEqual({ name: 'L', current_week: 3 })
  })

  it('non-2xx throws ApiError with status', async () => {
    mockFetch(503, { error: 'yahoo_unavailable', message: 'Yahoo is down' })
    const error = await getSeason().catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
    expect((error as ApiError).message).toBe('Yahoo is down')
  })

  it('non-JSON error body still throws ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>', { status: 502 })))
    const error = await getLeague().catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(502)
  })

  it('network failure throws Error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(getLeague()).rejects.toThrow('Failed to fetch')
  })
})
