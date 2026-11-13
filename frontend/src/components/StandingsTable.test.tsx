import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { finalSeason } from '../test/data'
import StandingsTable from './StandingsTable'

describe('StandingsTable', () => {
  it('names the champion with record and win %', () => {
    render(<StandingsTable standings={finalSeason().standings} rankings={finalSeason()} />)
    expect(screen.getByText('🏆 Champion: Team 4 — 118–60–2 (.661)')).toBeInTheDocument()
  })

  it('lists teams by rank with medals on the top three', () => {
    render(<StandingsTable standings={finalSeason().standings} rankings={finalSeason()} />)
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual([
      '#', 'Team', 'Record', 'Win %', 'Seed', 'Avg Rk', 'Med Rk', 'PTS Rk', 'FG% Rk', 'TO Rk',
    ])
    const rows = screen.getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell'))
    expect(rows.map((cells) => cells[0].className)).toEqual(['medal-gold', 'medal-silver', 'medal-bronze', ''])
    expect(rows[0].slice(0, 5).map((td) => td.textContent)).toEqual(['1', 'Team 4', '118–60–2', '.661', '1'])
    expect(rows[3][4].textContent).toBe('–')
  })

  it('shows no champion line without a rank-1 team', () => {
    const standings = finalSeason().standings.slice(1)
    render(<StandingsTable standings={standings} rankings={finalSeason()} />)
    expect(screen.queryByText(/Champion/)).toBeNull()
  })

  it('adds each team\'s avg, median and per-category stat ranks', () => {
    const season = finalSeason()
    season.teams[1] = { ...season.teams[1], avg_rank: 2.33, median_rank: 2, stats: { ...season.teams[1].stats, PTS: { value: 790, rank: 1 } } }
    render(<StandingsTable standings={season.standings} rankings={season} />)
    const rows = screen.getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell'))
    // Team 3 is 2nd in the standings and rows[1] in teams.
    expect(rows[1].slice(5).map((td) => td.textContent)).toEqual(['2.33', '2', '1', '2', '2'])
    expect(rows[1][5].className).toBe('')
    expect(rows[1][7].className).toBe('medal-gold')
    // Team 10 has no stats row: dashes, no crash.
    expect(rows[3].slice(5).map((td) => td.textContent)).toEqual(['–', '–', '–', '–', '–'])
  })
})
