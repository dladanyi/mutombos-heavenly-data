import type { Standing } from '../api'
import { formatValue, medal } from './RankCell'

const record = (s: Standing) => `${s.wins}–${s.losses}–${s.ties}`
const dash = (n: number | null) => (n === null ? '–' : String(n))

export default function StandingsTable({ standings }: { standings: Standing[] }) {
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
            </tr>
          </thead>
          <tbody>
            {standings.map((s) => {
              const color = s.rank === null ? undefined : medal(s.rank)
              return (
                <tr key={s.team_key}>
                  <td className={color ? `medal-${color}` : ''}>{dash(s.rank)}</td>
                  <td>{s.name}</td>
                  <td>{record(s)}</td>
                  <td>{formatValue(s.percentage, true)}</td>
                  <td>{dash(s.playoff_seed)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}
