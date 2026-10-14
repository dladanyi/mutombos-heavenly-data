import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { StatCell } from '../api'
import RankCell from './RankCell'

function renderCell(cell: StatCell, props: { percent?: boolean; showDetail?: boolean } = {}) {
  render(
    <table>
      <tbody>
        <tr>
          <RankCell cell={cell} {...props} />
        </tr>
      </tbody>
    </table>,
  )
  return Array.from(document.querySelectorAll('td'))
}

describe('RankCell', () => {
  it('applies medal classes for ranks 1-3 only', () => {
    const classes = [1, 2, 3, 4].map((rank) => {
      const [value, rankTd] = renderCell({ value: 10, rank })
      const result = [value.className, rankTd.className]
      document.body.innerHTML = ''
      return result
    })
    expect(classes).toEqual([
      ['medal-gold', 'rank-gold'],
      ['medal-silver', 'rank-silver'],
      ['medal-bronze', 'rank-bronze'],
      ['', ''],
    ])
  })

  it('renders dash for null', () => {
    const [value, rank] = renderCell({ value: null, rank: 12 })
    expect(value).toHaveTextContent('–')
    expect(rank).toHaveTextContent('12')
  })

  it('formats percent without leading zero', () => {
    renderCell({ value: 0.482, rank: 2 }, { percent: true })
    expect(screen.getByText('.482')).toBeInTheDocument()
  })

  it('pads percent to three decimals', () => {
    renderCell({ value: 0.5, rank: 2 }, { percent: true })
    expect(screen.getByText('.500')).toBeInTheDocument()
  })

  it('shows detail when present', () => {
    const tds = renderCell({ value: 0.482, rank: 1, detail: '301/624' }, { percent: true, showDetail: true })
    expect(tds).toHaveLength(3)
    expect(tds[2]).toHaveTextContent('301/624')
  })

  it('shows dash for missing detail', () => {
    const tds = renderCell({ value: null, rank: 4, detail: null }, { showDetail: true })
    expect(tds[2]).toHaveTextContent('–')
  })
})
