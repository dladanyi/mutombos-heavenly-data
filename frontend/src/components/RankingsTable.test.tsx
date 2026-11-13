import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { rankings, team } from '../test/data'
import RankingsTable from './RankingsTable'

describe('RankingsTable', () => {
  it('renders columns in category order', () => {
    render(<RankingsTable rankings={rankings()} />)
    const headers = screen.getAllByRole('columnheader').map((th) => th.textContent)
    expect(headers).toEqual(['Team', 'Avg Rank', 'Med Rank', 'PTS', 'PTS Rk', 'FG%', 'FG% Rk', 'FGM/FGA', 'TO', 'TO Rk'])
  })

  it('renders teams that share a name as separate rows', () => {
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
    const twins = [{ ...team('Same', 1), team_key: 'k.1' }, { ...team('Same', 2), team_key: 'k.2' }]
    render(<RankingsTable rankings={rankings({ teams: twins })} />)
    expect(screen.getAllByRole('row').slice(1)).toHaveLength(2)
    expect(errors.mock.calls.flat().join(' ')).not.toMatch(/same key/)
    errors.mockRestore()
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

  it('shows median rank uncolored next to avg rank', () => {
    const teams = [{ ...team('A', 1, 1.5), median_rank: 1 }, { ...team('B', 2, 2.25), median_rank: 2.5 }]
    render(<RankingsTable rankings={rankings({ teams })} />)
    const cells = screen.getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[2])
    expect(cells.map((td) => [td.textContent, td.className])).toEqual([
      ['1', ''],
      ['2.5', ''],
    ])
  })

  it('shows a dash when median rank is missing from older cached data', () => {
    const { median_rank: _, ...old } = team('A', 1)
    render(<RankingsTable rankings={rankings({ teams: [old] })} />)
    expect(within(screen.getAllByRole('row')[1]).getAllByRole('cell')[2].textContent).toBe('–')
  })

  it('renders team names as text', () => {
    const name = "<b>Mutombo's & 🏀</b>"
    render(<RankingsTable rankings={rankings({ teams: [team(name, 1)] })} />)
    expect(screen.getByText(name)).toBeInTheDocument()
    expect(document.querySelector('b')).toBeNull()
  })
})
