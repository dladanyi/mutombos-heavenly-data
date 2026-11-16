import type { TeamRow } from '../api'
import { medal } from './RankCell'
import { ResultCell } from './RankingsTable'
import { formatPct, formatWLT } from './allPlayFormat'

type Props = {
  /** Already in all-play order, each with all_play. */
  teams: TeamRow[]
  /** The week is in progress: the column is headed "Matchup" and coloured by who is leading. */
  live: boolean
}

/** One week's all-play standings: every team against every other team. */
export default function AllPlayTable({ teams, live }: Props) {
  return (
    <div className="table-wrap standings-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Team</th>
            <th>Avg Cats</th>
            <th>All-Play</th>
            <th>Win %</th>
            <th className="result-cell">{live ? 'Matchup' : 'Result'}</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((team) => {
            const ap = team.all_play!
            const color = medal(ap.place)
            return (
              <tr key={team.team_key}>
                <td className={color ? `medal-${color}` : ''}>{ap.place}</td>
                <td>{team.name}</td>
                <td>{ap.avg_cats.toFixed(2)}</td>
                <td>{formatWLT(ap)}</td>
                <td>{formatPct(ap.pct)}</td>
                <ResultCell result={team.result} live={live} />
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
