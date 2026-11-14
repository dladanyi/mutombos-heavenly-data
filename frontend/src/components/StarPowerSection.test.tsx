import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { seasonsList, starPower } from '../test/data'
import StarPowerSection from './StarPowerSection'

type Handler = () => Response
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

const back = () => screen.getByRole('button', { name: 'Previous season' })
const forward = () => screen.getByRole('button', { name: 'Next season' })

describe('StarPowerSection', () => {
  it('says when its own data is from', async () => {
    stubFetch({ '/api/stars': () => json(starPower({ fetched_at: '2026-11-20T18:30:00Z' })) })
    render(<StarPowerSection />)
    expect(await screen.findByText(/^As of /)).toHaveTextContent('Nov 20')
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('warns when Yahoo was unavailable and the data is stale', async () => {
    stubFetch({ '/api/stars': () => json(starPower({ stale: true })) })
    render(<StarPowerSection />)
    expect(await screen.findByRole('status')).toHaveTextContent(/Yahoo unavailable/)
  })

  it('opens on the current season with arrows and Refresh', async () => {
    const calls = stubFetch({ '/api/seasons': () => json(seasonsList()), '/api/stars': () => json(starPower()) })
    render(<StarPowerSection />)
    expect(await screen.findByText('2026-27')).toBeInTheDocument()
    expect(await screen.findByText(/Victor Wembanyama/)).toBeInTheDocument()
    expect(screen.getByText('Season to date · top 50')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument()
    expect(back()).toBeEnabled()
    expect(forward()).toBeDisabled()
    expect(calls.filter((u) => u.startsWith('/api/stars'))).toEqual(['/api/stars'])
  })

  it('steps back to a finished season: final ranks, end-of-season rosters, no Refresh', async () => {
    const past = starPower({ teams: [{ team_key: 't.9', name: 'Champs', place: 1, counts: { '10': 3, '25': 5, '50': 8 }, players: [] }] })
    const calls = stubFetch({
      '/api/seasons': () => json(seasonsList()),
      '/api/stars': () => json(starPower()),
      '/api/stars/2025': () => json({ ...past, season: 2025 }),
    })
    render(<StarPowerSection />)
    await userEvent.click(await screen.findByRole('button', { name: 'Previous season' }))
    expect(await screen.findByText('Champs')).toBeInTheDocument()
    expect(screen.getByText('2025-26')).toBeInTheDocument()
    expect(screen.getByText('Final · top 50')).toBeInTheDocument()
    expect(screen.getByText('Full-season ranks · rosters at season end')).toBeInTheDocument()
    expect(screen.queryByText(/^As of /)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Refresh' })).toBeNull()
    expect(back()).toBeDisabled()
    expect(calls).toContain('/api/stars/2025')
    await userEvent.click(forward())
    expect(await screen.findByText(/Victor Wembanyama/)).toBeInTheDocument()
  })

  it('in the off-season goes straight to the finished current season', async () => {
    const offSeason = seasonsList({ seasons: [{ season: 2026, league_key: '478.l.1', current: true, finished: true }] })
    const calls = stubFetch({
      '/api/seasons': () => json(offSeason),
      '/api/stars/2026': () => json({ ...starPower(), season: 2026 }),
    })
    render(<StarPowerSection />)
    expect(await screen.findByText('Final · top 50')).toBeInTheDocument()
    expect(await screen.findByText(/Victor Wembanyama/)).toBeInTheDocument()
    expect(calls.filter((u) => u.startsWith('/api/stars'))).toEqual(['/api/stars/2026'])
  })

  it('hides the arrows with one season', async () => {
    stubFetch({
      '/api/seasons': () => json(seasonsList({ seasons: [seasonsList().seasons[0]] })),
      '/api/stars': () => json(starPower()),
    })
    render(<StarPowerSection />)
    expect(await screen.findByText(/Victor Wembanyama/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Previous season' })).toBeNull()
  })
})
