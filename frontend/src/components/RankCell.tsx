import type { StatCell } from '../api'

const MEDALS = ['gold', 'silver', 'bronze']

export function medal(rank: number): string | undefined {
  return MEDALS[rank - 1]
}

export function formatValue(value: number | null, percent = false): string {
  if (value === null) return '–'
  return percent ? value.toFixed(3).replace(/^0/, '') : String(value)
}

type Props = { cell: StatCell; percent?: boolean; showDetail?: boolean }

/** One category for one team: value cell, rank cell, and optionally the made/attempted cell. */
export default function RankCell({ cell, percent = false, showDetail = false }: Props) {
  const color = medal(cell.rank)
  return (
    <>
      <td className={color ? `medal-${color}` : ''}>{formatValue(cell.value, percent)}</td>
      <td className={color ? `rank-${color}` : ''}>{cell.rank}</td>
      {showDetail && <td>{cell.detail ?? '–'}</td>}
    </>
  )
}
