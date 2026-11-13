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
      ['1.50', 'avg-rank medal-gold'],
      ['1.50', 'avg-rank medal-gold'],
      ['2.25', 'avg-rank medal-bronze'],
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

  it('shows a dash instead of crashing when median rank is null', () => {
    const teams = [{ ...team('A', 1), median_rank: null as unknown as number }]
    render(<RankingsTable rankings={rankings({ teams })} />)
    expect(within(screen.getAllByRole('row')[1]).getAllByRole('cell')[2].textContent).toBe('–')
  })

  it('renders team names as text', () => {
    const name = "<b>Mutombo's & 🏀</b>"
    render(<RankingsTable rankings={rankings({ teams: [team(name, 1)] })} />)
    expect(screen.getByText(name)).toBeInTheDocument()
    expect(document.querySelector('b')).toBeNull()
  })

  describe('result column', () => {
    const won = { outcome: 'W' as const, wins: 5, losses: 3, ties: 1, opponent: { team_key: 'k.b', name: 'Beta' } }
    const resultCells = () => screen.getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[1])

    it('is hidden unless asked for', () => {
      render(<RankingsTable rankings={rankings()} />)
      expect(screen.queryByRole('columnheader', { name: 'Result' })).toBeNull()
    })

    it('comes right after Team and shows outcome, score and opponent', () => {
      const teams = [
        { ...team('Alpha', 1), result: won },
        { ...team('Beta', 2), result: { ...won, outcome: 'L' as const, wins: 3, losses: 5, ties: 0, opponent: { team_key: 'k.a', name: 'Alpha' } } },
      ]
      render(<RankingsTable rankings={rankings({ teams })} showResult />)
      expect(screen.getAllByRole('columnheader').map((th) => th.textContent).slice(0, 3)).toEqual(['Team', 'Result', 'Avg Rank'])
      expect(resultCells().map((td) => td.textContent)).toEqual(['W 5–3–1 vs Beta', 'L 3–5 vs Alpha'])
      expect(within(resultCells()[0]).getByText('W 5–3–1')).toHaveClass('result-w')
      // Avg Rank is styled by class, so moving it to column 3 keeps its look.
      expect(within(screen.getAllByRole('row')[2]).getAllByRole('cell')[2]).toHaveClass('avg-rank')
    })

    it('shows the score without an outcome while unfinished, and a dash without a matchup', () => {
      const teams = [{ ...team('Alpha', 1), result: { ...won, outcome: null } }, { ...team('Beta', 2), result: null }, team('Gamma', 3)]
      render(<RankingsTable rankings={rankings({ teams })} showResult />)
      expect(resultCells().map((td) => td.textContent)).toEqual(['5–3–1 vs Beta', '–', '–'])
    })
  })
})
