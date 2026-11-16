import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AllPlaySeason, Rankings } from '../api'
import type { ApiState } from '../hooks/useApi'
import { allPlaySeason, rankings, team, withAllPlay } from '../test/data'
import AllPlaySection from './AllPlaySection'

function state<T>(data: T | undefined, extra: Partial<ApiState<T | undefined>> = {}): ApiState<T | undefined> {
  return { data, error: undefined, loading: false, refreshing: false, reload: vi.fn(async () => {}), ...extra }
}

const week = () => rankings({ state: 'current', teams: withAllPlay([team('Alpha', 1), team('Beta', 2), team('Gamma', 3)]) })

function show(weekState: ApiState<Rankings | undefined>, seasonState: ApiState<AllPlaySeason | undefined>) {
  return render(
    <AllPlaySection title="Week 7" badge={{ text: '● Live', live: true }} actions={null} week={weekState} live season={seasonState} />,
  )
}

describe('AllPlaySection', () => {
  it('renders the week table, the head-to-head grid and the season table in that order', () => {
    show(state(week()), state(allPlaySeason()))
    const titles = screen.getAllByText(/^(Week 7|Head-to-head|Season All-Play)$/).map((e) => e.textContent)
    expect(titles).toEqual(['Week 7', 'Head-to-head', 'Season All-Play'])
    expect(screen.getByText("Row team's category W–L–T vs each column team")).toBeInTheDocument()
    expect(screen.getByText('Weeks 1–6')).toBeInTheDocument()
    expect(document.querySelectorAll('table')).toHaveLength(3)
  })

  it('names a single counted week without a range', () => {
    show(state(week()), state(allPlaySeason({ weeks: 1, first_week: 1, last_week: 1 })))
    expect(screen.getByText('Week 1')).toBeInTheDocument()
  })

  it('says so when no week has finished yet', () => {
    show(state(week()), state(allPlaySeason({ weeks: 0, first_week: null, last_week: null, teams: [] })))
    expect(screen.getByText('No completed weeks yet')).toBeInTheDocument()
    expect(document.querySelectorAll('table')).toHaveLength(2)
  })

  it('asks for a reload when the week has no all-play numbers, and still shows the season', () => {
    show(state(rankings({ state: 'final' })), state(allPlaySeason()))
    expect(screen.getByText('Reload to see all-play numbers')).toBeInTheDocument()
    expect(screen.getByText('Season All-Play')).toBeInTheDocument()
    expect(document.querySelectorAll('table')).toHaveLength(1)
  })

  it('shows a skeleton while the week loads and a retry card when the season fails', async () => {
    const season = state<AllPlaySeason>(undefined, { error: new Error('Yahoo is unavailable') })
    show(state<Rankings>(undefined, { loading: true }), season)
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Yahoo is unavailable')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(season.reload).toHaveBeenCalled()
  })

  it('keeps the season table with a notice when a refresh fails', () => {
    show(state(week()), state(allPlaySeason(), { error: new Error('nope') }))
    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't update: nope")
    expect(screen.getByText('Season All-Play')).toBeInTheDocument()
  })

  it('season table: columns, Luck sign and colour, missing Record', () => {
    show(state(week()), state(allPlaySeason()))
    const table = document.querySelectorAll('table')[2] as HTMLElement
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual([
      '#', 'Team', 'All-Play', 'Win %', 'Avg Cats', 'Record', 'Luck',
    ])
    const rows = within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell'))
    expect(rows[0].map((c) => c.textContent)).toEqual(['1', 'Alpha', '19–3–1', '.700', '5.60', '30–20–4', '+0.25'])
    expect(rows[0][6]).toHaveClass('luck-pos')
    expect(rows[1][6]).toHaveTextContent('−0.75')
    expect(rows[1][6]).toHaveClass('luck-neg')
    expect(rows[2][5]).toHaveTextContent('–')
    expect(rows[2][6]).toHaveTextContent('0.00')
    expect(rows[2][6]).not.toHaveClass('luck-pos')
  })
})
