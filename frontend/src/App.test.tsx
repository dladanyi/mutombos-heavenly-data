import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { league, rankings } from './test/data'

type Route = { status?: number; body: unknown }
type Routes = Record<string, Route | Route[]>

function mockApi(routes: Routes) {
  const calls: string[] = []
  const fetchMock = vi.fn(async (url: string) => {
    calls.push(url)
    const path = url.replace('?refresh=1', '')
    const entry = routes[path]
    if (!entry) return new Response(JSON.stringify({ error: 'not_found' }), { status: 404 })
    const route = Array.isArray(entry) ? (entry.length > 1 ? entry.shift()! : entry[0]) : entry
    return new Response(JSON.stringify(route.body), { status: route.status ?? 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

function happyRoutes(): Routes {
  return {
    '/api/league': { body: league() },
    '/api/rankings/week/current': { body: rankings() },
    '/api/rankings/season': { body: rankings({ scope: 'season', week: null }) },
    '/api/rankings/week/6': { body: rankings({ week: 6 }) },
  }
}

describe('App', () => {
  it('shows loading then three sections', async () => {
    mockApi(happyRoutes())
    render(<App />)
    expect(document.querySelectorAll('.skeleton').length).toBeGreaterThan(0)
    expect(await screen.findByText('Week 7')).toBeInTheDocument()
    expect(screen.getByText('Full Season')).toBeInTheDocument()
    expect(await screen.findByText('Week 6')).toBeInTheDocument()
    await waitFor(() => expect(document.querySelectorAll('table')).toHaveLength(3))
    expect(screen.getByText(/Last updated:/)).toHaveTextContent('Nov 20, 2026')
  })

  it('hides last week in week 1', async () => {
    const routes = happyRoutes()
    routes['/api/league'] = { body: league({ current_week: 1 }) }
    routes['/api/rankings/week/current'] = { body: rankings({ week: 1 }) }
    const calls = mockApi(routes)
    render(<App />)
    expect(await screen.findByText('Week 1')).toBeInTheDocument()
    await waitFor(() => expect(document.querySelectorAll('table')).toHaveLength(2))
    expect(screen.queryByText('Week 0')).toBeNull()
    expect(calls.some((c) => c.includes('/week/0'))).toBe(false)
  })

  it('shows error card and retries', async () => {
    const routes = happyRoutes()
    routes['/api/rankings/season'] = [
      { status: 503, body: { error: 'yahoo_unavailable', message: 'Yahoo Fantasy is unavailable right now.' } },
      { body: rankings({ scope: 'season', week: null }) },
    ]
    mockApi(routes)
    render(<App />)
    expect(await screen.findByText('Yahoo Fantasy is unavailable right now.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(document.querySelectorAll('table')).toHaveLength(3))
    expect(screen.queryByText('Yahoo Fantasy is unavailable right now.')).toBeNull()
  })

  it('shows stale notice', async () => {
    const routes = happyRoutes()
    routes['/api/rankings/week/current'] = { body: rankings({ stale: true }) }
    mockApi(routes)
    render(<App />)
    expect(await screen.findByText(/Showing data as of/)).toBeInTheDocument()
  })

  it('refresh sends refresh=1', async () => {
    const calls = mockApi(happyRoutes())
    render(<App />)
    await screen.findByText('Week 6')
    await userEvent.click(screen.getByRole('button', { name: /Refresh/ }))
    await waitFor(() => {
      expect(calls).toContain('/api/rankings/week/current?refresh=1')
      expect(calls).toContain('/api/rankings/season?refresh=1')
      expect(calls).toContain('/api/rankings/week/6?refresh=1')
    })
  })

  it('says just refreshed when every refresh was throttled', async () => {
    const routes = happyRoutes()
    for (const path of ['/api/rankings/week/current', '/api/rankings/season', '/api/rankings/week/6']) {
      const body = (routes[path] as Route).body as object
      routes[path] = [{ body }, { body: { ...body, refresh_throttled: true } }]
    }
    mockApi(routes)
    render(<App />)
    await screen.findByText('Week 6')
    await userEvent.click(screen.getByRole('button', { name: /Refresh/ }))
    expect(await screen.findByText('Just refreshed')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('Just refreshed')).toBeNull(), { timeout: 4000 })
  })
})
