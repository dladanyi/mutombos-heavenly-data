import type { RankingsTableData, Standing } from '../api'
import { formatValue, medal } from './RankCell'

const record = (s: Standing) => `${s.wins}–${s.losses}–${s.ties}`
const dash = (n: number | null) => (n === null ? '–' : String(n))

type Props = {
  standings: Standing[]
  /** The season's stat rankings; each standings row shows its team's ranks from it. */
  rankings: RankingsTableData
}

export default function StandingsTable({ standings, rankings }: Props) {
  const rowsByTeam = new Map(rankings.teams.map((t) => [t.team_key, t]))
  const champion = standings.find((s) => s.rank === 1)
  return (
    <>
      {champion && (
        <div className="champion">
          🏆 Champion: {champion.name} — {record(champion)} ({formatValue(champion.percentage, true)})
        </div>
      )}
      <div className="table-wrap standings-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Team</th>
              <th>Record</th>
              <th>Win %</th>
              <th>Seed</th>
              <th>Avg Rk</th>
              <th>Med Rk</th>
              {rankings.categories.map((c) => (
                <th key={c.key}>{c.key} Rk</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {standings.map((s) => {
              const color = s.rank === null ? undefined : medal(s.rank)
              const ranks = rowsByTeam.get(s.team_key)
              return (
                <tr key={s.team_key}>
                  <td className={color ? `medal-${color}` : ''}>{dash(s.rank)}</td>
                  <td>{s.name}</td>
                  <td>{record(s)}</td>
                  <td>{formatValue(s.percentage, true)}</td>
                  <td>{dash(s.playoff_seed)}</td>
                  <td>{ranks ? ranks.avg_rank.toFixed(2) : '–'}</td>
                  <td>{ranks?.median_rank ?? '–'}</td>
                  {rankings.categories.map((c) => {
                    const rank = ranks?.stats[c.key]?.rank
                    const statColor = rank === undefined ? undefined : medal(rank)
                    return (
                      <td key={c.key} className={statColor ? `medal-${statColor}` : ''}>
                        {rank ?? '–'}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}
