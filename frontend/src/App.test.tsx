import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { finalSeason, league, rankings, seasonsList, starPower } from './test/data'

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
    '/api/rankings/week/current': { body: rankings({ state: 'current' }) },
    '/api/rankings/season': { body: rankings({ scope: 'season', week: null }) },
    '/api/rankings/week/6': { body: rankings({ week: 6, state: 'final' }) },
    '/api/seasons': { body: seasonsList() },
    '/api/stars': { body: starPower() },
  }
}

describe('App', () => {
  beforeEach(() => {
    window.location.hash = ''
  })

  it('opens on the Rankings tab without loading Star Power', async () => {
    const calls = mockApi(happyRoutes())
    render(<App />)
    expect(await screen.findByRole('tab', { name: 'Rankings' })).toHaveAttribute('aria-selected', 'true')
    await screen.findByText('Week 7')
    expect(calls).not.toContain('/api/stars')
  })

  it('switches to Star Power and back with the tabs and the URL hash', async () => {
    const calls = mockApi(happyRoutes())
    render(<App />)
    await userEvent.click(await screen.findByRole('tab', { name: 'Star Power' }))
    expect(window.location.hash).toBe('#stars')
    expect(await screen.findByText('Not on a team: 37 Player X (FA) · 48 Player Y (W)')).toBeInTheDocument()
    expect(calls).toContain('/api/stars')
    expect(screen.getByText('Week 7')).not.toBeVisible()
    window.location.hash = ''
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    expect(await screen.findByText('Week 7')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Rankings' })).toHaveAttribute('aria-selected', 'true')
  })

  it('keeps each tab loaded after switching away and back', async () => {
    const calls = mockApi(happyRoutes())
    render(<App />)
    await userEvent.click(await screen.findByRole('tab', { name: 'Star Power' }))
    await screen.findByText(/Not on a team/)
    await userEvent.click(screen.getByRole('tab', { name: 'Rankings' }))
    await userEvent.click(screen.getByRole('tab', { name: 'Star Power' }))
    expect(screen.getByText(/Not on a team/)).toBeVisible()
    expect(calls.filter((c) => c === '/api/stars')).toHaveLength(1)
  })

  it('leaves the URL clean and history untouched when choosing tabs', async () => {
    mockApi(happyRoutes())
    render(<App />)
    const before = window.history.length
    await userEvent.click(await screen.findByRole('tab', { name: 'Rankings' }))
    expect(window.history.length).toBe(before)
    await userEvent.click(screen.getByRole('tab', { name: 'Star Power' }))
    await userEvent.click(screen.getByRole('tab', { name: 'Rankings' }))
    expect(window.location.href.endsWith('#')).toBe(false)
    expect(window.location.hash).toBe('')
  })

  it('hides the rankings timestamp in the header on Star Power', async () => {
    mockApi(happyRoutes())
    render(<App />)
    await screen.findByText(/Last updated:/)
    await userEvent.click(screen.getByRole('tab', { name: 'Star Power' }))
    await screen.findByText(/Not on a team/)
    expect(screen.queryByText(/Last updated:/)).toBeNull()
  })

  it('opens Star Power when the page loads with #stars', async () => {
    window.location.hash = '#stars'
    mockApi(happyRoutes())
    render(<App />)
    expect(await screen.findByRole('tab', { name: 'Star Power' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByText(/Not on a team/)).toBeInTheDocument()
  })

  it('shows loading then the week and full season sections', async () => {
    mockApi(happyRoutes())
    render(<App />)
    expect(document.querySelectorAll('.skeleton').length).toBeGreaterThan(0)
    expect(await screen.findByText('Week 7')).toBeInTheDocument()
    expect(screen.getByText('Full Season')).toBeInTheDocument()
    await waitFor(() => expect(document.querySelectorAll('table')).toHaveLength(2))
    expect(screen.queryByText('Last week')).toBeNull()
    expect(screen.getByText(/Last updated:/)).toHaveTextContent('Nov 20, 2026')
  })

  it('steps back through weeks with the arrows and forward to the live week', async () => {
    const calls = mockApi(happyRoutes())
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Previous week' }))
    expect(await screen.findByText('Week 6')).toBeInTheDocument()
    expect(calls).toContain('/api/rankings/week/6')
    expect(screen.getByText('Final')).toBeInTheDocument()
    await waitFor(() => expect(document.querySelectorAll('table')).toHaveLength(2))
    expect(document.querySelector('table th:nth-child(2)')!.textContent).toBe('Result')
    expect(screen.queryByText('● Live')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Next week' }))
    expect(await screen.findByText('Week 7')).toBeInTheDocument()
    expect(screen.getByText('● Live')).toBeInTheDocument()
    expect(document.querySelector('table th:nth-child(2)')!.textContent).toBe('Matchup')
    expect(screen.getByRole('button', { name: 'Next week' })).toBeDisabled()
  })

  it('stops at the league\'s first week', async () => {
    const routes = happyRoutes()
    routes['/api/league'] = { body: league({ start_week: 6 }) }
    mockApi(routes)
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Previous week' }))
    expect(await screen.findByText('Week 6')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous week' })).toBeDisabled()
  })

  it('shows a settling badge for a week inside the stat-correction window', async () => {
    const routes = happyRoutes()
    routes['/api/rankings/week/6'] = { body: rankings({ week: 6, state: 'settling' }) }
    mockApi(routes)
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Previous week' }))
    expect(await screen.findByText('Settling')).toBeInTheDocument()
  })

  it('has no week arrows in week 1', async () => {
    const routes = happyRoutes()
    routes['/api/league'] = { body: league({ current_week: 1 }) }
    routes['/api/rankings/week/current'] = { body: rankings({ week: 1 }) }
    const calls = mockApi(routes)
    render(<App />)
    expect(await screen.findByText('Week 1')).toBeInTheDocument()
    await waitFor(() => expect(document.querySelectorAll('table')).toHaveLength(2))
    expect(screen.queryByRole('button', { name: 'Previous week' })).toBeNull()
    expect(calls.some((c) => c.includes('/week/0'))).toBe(false)
  })

  it('refresh still reloads the current season while it shows its final view', async () => {
    const routes = happyRoutes()
    routes['/api/seasons'] = { body: seasonsList({ seasons: [{ season: 2026, league_key: '478.l.1', current: true, finished: true }] }) }
    routes['/api/seasons/2026'] = { body: finalSeason({ season: 2026 }) }
    const calls = mockApi(routes)
    render(<App />)
    expect(await screen.findByText(/Champion/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Refresh/ }))
    await waitFor(() => expect(calls).toContain('/api/rankings/season?refresh=1'))
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
    await waitFor(() => expect(document.querySelectorAll('table')).toHaveLength(2))
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
    await screen.findByText('Week 7')
    await userEvent.click(screen.getByRole('button', { name: /Refresh/ }))
    await waitFor(() => {
      expect(calls).toContain('/api/rankings/week/current?refresh=1')
      expect(calls).toContain('/api/rankings/season?refresh=1')
    })
  })

  it('refresh also reloads the past week being viewed', async () => {
    const calls = mockApi(happyRoutes())
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Previous week' }))
    await screen.findByText('Week 6')
    await userEvent.click(screen.getByRole('button', { name: /Refresh/ }))
    await waitFor(() => {
      expect(calls).toContain('/api/rankings/week/6?refresh=1')
      expect(calls).toContain('/api/rankings/week/current?refresh=1')
    })
  })

  it('says just refreshed when a final week ignores refresh', async () => {
    const routes = happyRoutes()
    for (const path of ['/api/rankings/week/current', '/api/rankings/season']) {
      const body = (routes[path] as Route).body as object
      routes[path] = [{ body }, { body: { ...body, refresh_throttled: true } }]
    }
    mockApi(routes)
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Previous week' }))
    await screen.findByText('Week 6')
    await userEvent.click(screen.getByRole('button', { name: /Refresh/ }))
    expect(await screen.findByText('Just refreshed')).toBeInTheDocument()
  })

  it('shows a notice when a refresh fails but keeps the table', async () => {
    const routes = happyRoutes()
    routes['/api/rankings/season'] = [
      { body: rankings({ scope: 'season', week: null }) },
      { status: 503, body: { error: 'yahoo_unavailable', message: 'Yahoo Fantasy is unavailable right now.' } },
    ]
    mockApi(routes)
    render(<App />)
    await screen.findByText('Week 7')
    await waitFor(() => expect(document.querySelectorAll('table')).toHaveLength(2))
    await userEvent.click(screen.getByRole('button', { name: /Refresh/ }))
    expect(await screen.findByText(/Couldn't update: Yahoo Fantasy is unavailable right now\./)).toBeInTheDocument()
    expect(document.querySelectorAll('table')).toHaveLength(2)
  })

  it('drops the live badge once the season is over', async () => {
    const routes = happyRoutes()
    routes['/api/rankings/week/current'] = { body: rankings({ week: 21, state: 'final' }) }
    routes['/api/league'] = { body: league({ current_week: 21 }) }
    mockApi(routes)
    render(<App />)
    expect(await screen.findByText('Season over')).toBeInTheDocument()
    expect(screen.queryByText('● Live')).toBeNull()
    await waitFor(() => expect(document.querySelectorAll('table')).toHaveLength(2))
    expect(document.querySelector('table th:nth-child(2)')!.textContent).toBe('Result')
  })

  it('keeps the live badge when a mid-season week has ended', async () => {
    const routes = happyRoutes()
    routes['/api/rankings/week/current'] = { body: rankings({ state: 'settling' }) }
    mockApi(routes)
    render(<App />)
    await screen.findByText('Week 7')
    expect(screen.getByText('● Live')).toBeInTheDocument()
  })

  it('says just refreshed when every refresh was throttled', async () => {
    const routes = happyRoutes()
    for (const path of ['/api/rankings/week/current', '/api/rankings/season']) {
      const body = (routes[path] as Route).body as object
      routes[path] = [{ body }, { body: { ...body, refresh_throttled: true } }]
    }
    mockApi(routes)
    render(<App />)
    await screen.findByText('Week 7')
    await waitFor(() => expect(document.querySelectorAll('table')).toHaveLength(2))
    await userEvent.click(screen.getByRole('button', { name: /Refresh/ }))
    expect(await screen.findByText('Just refreshed')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('Just refreshed')).toBeNull(), { timeout: 4000 })
  })

  it('keeps showing the chosen week when Yahoo rolls over to a new week', async () => {
    const routes = happyRoutes()
    routes['/api/league'] = [{ body: league() }, { body: league({ current_week: 8 }) }]
    mockApi(routes)
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Previous week' }))
    expect(await screen.findByText('Week 6')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Refresh/ }))
    await new Promise((r) => setTimeout(r, 50))
    expect(screen.getByText('Week 6')).toBeInTheDocument()
    expect(screen.queryByText('Week 7')).toBeNull()
  })

  it('shows no state badge for a past week that has not loaded', async () => {
    const routes = happyRoutes()
    routes['/api/rankings/week/6'] = { status: 503, body: { error: 'yahoo_unavailable', message: 'down' } }
    mockApi(routes)
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Previous week' }))
    expect(await screen.findByText('down')).toBeInTheDocument()
    expect(screen.queryByText('Final')).toBeNull()
    expect(screen.queryByText('Settling')).toBeNull()
  })
})
