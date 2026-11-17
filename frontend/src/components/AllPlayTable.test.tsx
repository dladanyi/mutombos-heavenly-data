import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { team, withAllPlay } from '../test/data'
import AllPlayTable from './AllPlayTable'
import { byAllPlayOrder, formatLuck, formatPct, formatWLT } from './allPlayFormat'

const teams = () => withAllPlay([team('Alpha', 1), team('Beta', 2), team('Gamma', 3), team('Delta', 4)])

describe('allPlayFormat', () => {
  it('formats records, Win % and Luck', () => {
    expect(formatWLT({ wins: 9, losses: 1, ties: 0 })).toBe('9–1–0')
    expect([formatPct(0.9), formatPct(1), formatPct(0)]).toEqual(['.900', '1.000', '.000'])
    expect([formatLuck(0.25), formatLuck(-0.75), formatLuck(0), formatLuck(-0.001), formatLuck(null)]).toEqual([
      '+0.25', '−0.75', '0.00', '0.00', '–',
    ])
  })

  it('orders by all_play.order and drops rows without all-play numbers', () => {
    const [a, b, c] = teams()
    const shuffled = [c, a, { ...b, all_play: undefined }]
    expect(byAllPlayOrder(shuffled).map((t) => t.name)).toEqual(['Alpha', 'Gamma'])
  })
})

describe('AllPlayTable', () => {
  it('shows place, Avg Cats, the all-play record, Win % and the real matchup', () => {
    const rows = teams()
    rows[0].result = { outcome: null, wins: 5, losses: 3, ties: 1, opponent: { team_key: 'x', name: 'Beta' } }
    render(<AllPlayTable teams={rows} live />)
    const headers = screen.getAllByRole('columnheader').map((th) => th.textContent)
    expect(headers).toEqual(['#', 'Team', 'Avg Cats', 'All-Play', 'Win %', 'Matchup'])
    const first = within(screen.getAllByRole('row')[1]).getAllByRole('cell')
    expect(first.map((c) => c.textContent)).toEqual(['1', 'Alpha', '6.00', '3–0–0', '1.000', '5–3–1 vs Beta'])
    expect(first[0]).toHaveClass('medal-gold')
  })

  it('heads the matchup column "Result" for a finished week', () => {
    render(<AllPlayTable teams={teams()} live={false} />)
    expect(screen.getAllByRole('columnheader').at(-1)).toHaveTextContent('Result')
  })
})
