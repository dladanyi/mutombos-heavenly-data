import type { TeamRow } from '../api'
import ColumnHelp from './ColumnHelp'
import { WEEK_HELP } from './columnHelpText'
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
            <th><ColumnHelp label="Avg Cats">{WEEK_HELP['Avg Cats']}</ColumnHelp></th>
            <th><ColumnHelp label="All-Play">{WEEK_HELP['All-Play']}</ColumnHelp></th>
            <th><ColumnHelp label="Win %">{WEEK_HELP['Win %']}</ColumnHelp></th>
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
