import type { AllPlaySeason } from '../api'
import { medal } from './RankCell'
import { formatLuck, formatPct, formatWLT } from './allPlayFormat'

const luckClass = (luck: number | null) =>
  luck === null || formatLuck(luck) === '0.00' ? '' : luck > 0 ? 'luck-pos' : 'luck-neg'

/** Weekly all-play summed over the season's completed weeks, with the real record and Luck. */
export default function AllPlaySeasonTable({ data }: { data: AllPlaySeason }) {
  return (
    <div className="table-wrap standings-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Team</th>
            <th>All-Play</th>
            <th>Win %</th>
            <th>Avg Cats</th>
            <th>Record</th>
            <th>Luck</th>
          </tr>
        </thead>
        <tbody>
          {data.teams.map((t) => {
            const color = medal(t.place)
            return (
              <tr key={t.team_key}>
                <td className={color ? `medal-${color}` : ''}>{t.place}</td>
                <td>{t.name}</td>
                <td>{formatWLT(t)}</td>
                <td>{formatPct(t.pct)}</td>
                <td>{t.avg_cats.toFixed(2)}</td>
                <td>{t.record ? formatWLT(t.record) : '–'}</td>
                <td className={luckClass(t.luck)}>{formatLuck(t.luck)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
