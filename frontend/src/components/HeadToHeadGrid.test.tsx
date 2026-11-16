import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { team, withAllPlay } from '../test/data'
import HeadToHeadGrid from './HeadToHeadGrid'

describe('HeadToHeadGrid', () => {
  it('shows each pairing from the row team’s side, with a dash on the diagonal', () => {
    render(<HeadToHeadGrid teams={withAllPlay([team('Alpha', 1), team('Beta', 2)])} />)
    const headers = screen.getAllByRole('columnheader')
    expect(headers.map((th) => th.textContent)).toEqual(['Team', 'Alpha', 'Beta'])
    expect(headers[1]).toHaveAttribute('title', 'Alpha')
    const [alpha, beta] = screen.getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell'))
    expect(alpha.map((c) => c.textContent)).toEqual(['Alpha', '—', '6–3–0'])
    expect(beta.map((c) => c.textContent)).toEqual(['Beta', '3–6–0', '—'])
    expect(alpha[2]).toHaveClass('h2h-w')
    expect(beta[1]).toHaveClass('h2h-l')
  })

  it('shades a tied pairing as a tie', () => {
    const [a, b] = withAllPlay([team('Alpha', 1), team('Beta', 2)])
    a.all_play!.vs[b.team_key] = { wins: 4, losses: 4, ties: 1 }
    render(<HeadToHeadGrid teams={[a, b]} />)
    expect(screen.getByText('4–4–1')).toHaveClass('h2h-t')
  })
})
