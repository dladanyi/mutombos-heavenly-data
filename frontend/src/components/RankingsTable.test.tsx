import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { rankings, team } from '../test/data'
import RankingsTable from './RankingsTable'

describe('RankingsTable', () => {
  it('renders columns in category order', () => {
    render(<RankingsTable rankings={rankings()} />)
    const headers = screen.getAllByRole('columnheader').map((th) => th.textContent)
    expect(headers).toEqual(['Team', 'Avg Rank', 'PTS', 'PTS Rk', 'FG%', 'FG% Rk', 'FGM/FGA', 'TO', 'TO Rk'])
  })

  it('renders one row per team in API order', () => {
    render(<RankingsTable rankings={rankings()} />)
    const rows = screen.getAllByRole('row').slice(1)
    expect(rows.map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['Alpha', 'Beta', 'Gamma', 'Delta'])
  })

  it('colors avg rank by place', () => {
    render(<RankingsTable rankings={rankings({ teams: [team('A', 1, 1.5), team('B', 1, 1.5), team('C', 3, 2.25)] })} />)
    const avgCells = screen.getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[1])
    expect(avgCells.map((td) => [td.textContent, td.className])).toEqual([
      ['1.50', 'medal-gold'],
      ['1.50', 'medal-gold'],
      ['2.25', 'medal-bronze'],
    ])
  })

  it('renders team names as text', () => {
    const name = "<b>Mutombo's & 🏀</b>"
    render(<RankingsTable rankings={rankings({ teams: [team(name, 1)] })} />)
    expect(screen.getByText(name)).toBeInTheDocument()
    expect(document.querySelector('b')).toBeNull()
  })
})
