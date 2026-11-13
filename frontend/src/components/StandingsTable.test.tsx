import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { finalSeason } from '../test/data'
import StandingsTable from './StandingsTable'

describe('StandingsTable', () => {
  it('names the champion with record and win %', () => {
    render(<StandingsTable standings={finalSeason().standings} />)
    expect(screen.getByText('🏆 Champion: Team 4 — 118–60–2 (.661)')).toBeInTheDocument()
  })

  it('lists teams by rank with medals on the top three', () => {
    render(<StandingsTable standings={finalSeason().standings} />)
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['#', 'Team', 'Record', 'Win %', 'Seed'])
    const rows = screen.getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell'))
    expect(rows.map((cells) => cells[0].className)).toEqual(['medal-gold', 'medal-silver', 'medal-bronze', ''])
    expect(rows[0].map((td) => td.textContent)).toEqual(['1', 'Team 4', '118–60–2', '.661', '1'])
    expect(rows[3][4].textContent).toBe('–')
  })

  it('shows no champion line without a rank-1 team', () => {
    const standings = finalSeason().standings.slice(1)
    render(<StandingsTable standings={standings} />)
    expect(screen.queryByText(/Champion/)).toBeNull()
  })
})
