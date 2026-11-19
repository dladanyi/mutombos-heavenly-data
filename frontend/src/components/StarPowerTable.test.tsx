import { cleanup, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { starPower } from '../test/data'
import StarPowerTable from './StarPowerTable'

const teamRows = () => [...document.querySelectorAll('tr.star-team')]
const playerLines = () => [...document.querySelectorAll('tr.star-players')]

describe('StarPowerTable', () => {
  it('ranks teams with their top-10/25/50 counts and medals', () => {
    render(<StarPowerTable data={starPower()} />)
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['#', 'Team', 'Top 10', 'Top 25', 'Top 50'])
    const cells = teamRows().map((r) => within(r as HTMLElement).getAllByRole('cell'))
    expect(cells[0].map((td) => td.textContent)).toEqual(['1', 'Alpha', '2', '3', '4'])
    expect(cells.map((c) => c[0].className)).toEqual(['medal-gold', 'medal-silver', 'medal-bronze', ''])
  })

  it('lists each team\'s players by rank with a star for the top 10', () => {
    render(<StarPowerTable data={starPower()} />)
    const players = [...playerLines()[0].querySelectorAll('.star-player')].map((p) => p.textContent)
    expect(players[0]).toBe('★ 1 Victor Wembanyama SAS C')
    expect(players[2]).toBe('14 Player Fourteen SAS C')
    expect(playerLines()[3].textContent).toBe('No top-50 players')
  })

  const tiersFor = (levels: number[], ranks: number[]) => {
    const base = starPower()
    const players = ranks.map((rank) => ({ ...base.teams[0].players[0], rank, player_key: `p.${rank}` }))
    render(<StarPowerTable data={{ ...base, levels, teams: [{ ...base.teams[0], players }] }} />)
    return [...playerLines()[0].querySelectorAll('.star-player')].map((p) => [
      ['star-gold', 'star-silver', 'star-bronze'].find((c) => p.classList.contains(c)) ?? '',
      p.textContent!.startsWith('★'),
    ])
  }

  it('colours players by tier: gold (starred) top 10, silver 11-25, bronze 26-50', () => {
    expect(tiersFor([10, 25, 50], [10, 11, 25, 26, 50])).toEqual([
      ['star-gold', true], ['star-silver', false], ['star-silver', false], ['star-bronze', false], ['star-bronze', false],
    ])
  })

  it('takes the tiers from the response levels, in any order', () => {
    const expected = [['star-gold', true], ['star-silver', false], ['star-silver', false], ['star-bronze', false]]
    expect(tiersFor([5, 20, 50], [5, 6, 20, 21])).toEqual(expected)
    cleanup()
    expect(tiersFor([50, 5, 20], [5, 6, 20, 21])).toEqual(expected)
  })

  const unownedLine = () => document.querySelector('.star-unowned')

  it('lists top-50 players who are on no team', () => {
    render(<StarPowerTable data={starPower()} />)
    expect(unownedLine()).toHaveTextContent(/^Not on a team: 37 Player X \(FA\) · 48 Player Y \(W\)$/)
  })

  it('labels a top-50 player whose team is not in the league list', () => {
    const data = starPower({ unowned: [{ rank: 17, player_key: 'p.17', name: 'Player Z', nba_team: 'NYK', position: 'SF', status: 'team' }] })
    render(<StarPowerTable data={data} />)
    expect(unownedLine()).toHaveTextContent(/^Not on a team: 17 Player Z \(other team\)$/)
  })

  it('colours unowned players by tier too, with the star for the top 10', () => {
    const base = starPower().unowned[0]
    const unowned = [5, 11, 26].map((rank) => ({ ...base, rank, player_key: `p.${rank}`, name: `Player ${rank}` }))
    render(<StarPowerTable data={starPower({ unowned })} />)
    const players = [...unownedLine()!.querySelectorAll('.star-player')]
    expect(players.map((p) => [p.className, p.textContent])).toEqual([
      ['star-player star-gold', '★ 5 Player 5 (FA)'],
      ['star-player star-silver', '11 Player 11 (FA)'],
      ['star-player star-bronze', '26 Player 26 (FA)'],
    ])
  })

  it('omits the unowned line when every top-50 player is on a team', () => {
    render(<StarPowerTable data={starPower({ unowned: [] })} />)
    expect(screen.queryByText(/Not on a team/)).toBeNull()
  })
})
