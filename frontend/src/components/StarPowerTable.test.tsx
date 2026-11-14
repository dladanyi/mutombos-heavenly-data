import { render, screen, within } from '@testing-library/react'
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

  it('lists top-50 players who are on no team', () => {
    render(<StarPowerTable data={starPower()} />)
    expect(screen.getByText('Not on a team: 37 Player X (FA) · 48 Player Y (W)')).toBeInTheDocument()
  })

  it('omits the unowned line when every top-50 player is on a team', () => {
    render(<StarPowerTable data={starPower({ unowned: [] })} />)
    expect(screen.queryByText(/Not on a team/)).toBeNull()
  })
})
