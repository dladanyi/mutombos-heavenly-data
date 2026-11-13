import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Rankings } from '../api'
import type { ApiState } from '../hooks/useApi'
import { finalSeason, rankings, seasonsList } from '../test/data'
import FullSeasonSection from './FullSeasonSection'

type Handler = () => Promise<Response> | Response
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

function stubFetch(routes: Record<string, Handler>) {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    calls.push(url)
    const handler = routes[url]
    return handler ? handler() : json({ error: 'not_found' }, 404)
  }))
  return calls
}

function current(): ApiState<Rankings> {
  return { data: rankings({ scope: 'season', week: null }), error: undefined, loading: false, refreshing: false, reload: async () => {} }
}

const tables = () => [...document.querySelectorAll('table')]
const back = () => screen.getByRole('button', { name: 'Previous season' })
const forward = () => screen.getByRole('button', { name: 'Next season' })

describe('FullSeasonSection', () => {
  it('opens on the current in-progress season with today\'s view', async () => {
    stubFetch({ '/api/seasons': () => json(seasonsList()) })
    render(<FullSeasonSection current={current()} onRetry={() => {}} />)
    expect(await screen.findByText('2026-27')).toBeInTheDocument()
    expect(screen.getByText('Season to date')).toBeInTheDocument()
    expect(back()).toBeEnabled()
    expect(forward()).toBeDisabled()
    expect(tables()).toHaveLength(1)
  })

  it('steps back to a finished season with standings and plain avg rank', async () => {
    stubFetch({ '/api/seasons': () => json(seasonsList()), '/api/seasons/2025': () => json(finalSeason()) })
    render(<FullSeasonSection current={current()} onRetry={() => {}} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Previous season' }))
    expect(await screen.findByText('🏆 Champion: Team 4 — 118–60–2 (.661)')).toBeInTheDocument()
    expect(screen.getByText('2025-26')).toBeInTheDocument()
    expect(screen.getByText('Final')).toBeInTheDocument()
    expect(screen.getByText('Season totals, including playoffs')).toBeInTheDocument()
    expect(tables()).toHaveLength(2)
    expect([...tables()[1].querySelectorAll('td.avg-rank')].some((td) => td.className.includes('medal-'))).toBe(false)
    expect(back()).toBeDisabled()
    expect(forward()).toBeEnabled()
  })

  it.each([
    ['one season', () => json(seasonsList({ seasons: [seasonsList().seasons[0]] }))],
    ['a failed list', () => json({ error: 'internal' }, 500)],
  ])('hides the arrows with %s', async (_, handler) => {
    stubFetch({ '/api/seasons': handler })
    render(<FullSeasonSection current={current()} onRetry={() => {}} />)
    await waitFor(() => expect(tables()).toHaveLength(1))
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.queryByRole('button', { name: 'Previous season' })).toBeNull()
    expect(screen.getByText('Season to date')).toBeInTheDocument()
  })

  it('still offers the seasons found when the list is incomplete', async () => {
    stubFetch({ '/api/seasons': () => json(seasonsList({ complete: false })) })
    render(<FullSeasonSection current={current()} onRetry={() => {}} />)
    expect(await screen.findByRole('button', { name: 'Previous season' })).toBeEnabled()
  })

  it('never shows a slow season under another season\'s label', async () => {
    let release: () => void = () => {}
    const slow = new Promise<void>((r) => { release = r })
    stubFetch({
      '/api/seasons': () => json(seasonsList()),
      '/api/seasons/2025': async () => { await slow; return json(finalSeason()) },
    })
    render(<FullSeasonSection current={current()} onRetry={() => {}} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Previous season' }))
    await userEvent.click(forward())
    release()
    await new Promise((r) => setTimeout(r, 10))
    expect(screen.getByText('2026-27')).toBeInTheDocument()
    expect(screen.queryByText(/Champion/)).toBeNull()
    expect(tables()).toHaveLength(1)
  })

  it('opens a finished current season on its final view', async () => {
    const calls = stubFetch({
      '/api/seasons': () => json(seasonsList({ seasons: [{ season: 2026, league_key: '478.l.1', current: true, finished: true }] })),
      '/api/seasons/2026': () => json(finalSeason({ season: 2026 })),
    })
    render(<FullSeasonSection current={current()} onRetry={() => {}} />)
    expect(await screen.findByText(/Champion/)).toBeInTheDocument()
    expect(screen.getByText('Final')).toBeInTheDocument()
    expect(calls).toContain('/api/seasons/2026')
    expect(within(tables()[0]).getAllByRole('columnheader')[0].textContent).toBe('#')
  })
})
