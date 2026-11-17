import type { TeamRow } from '../api'
import { formatWLT, tone } from './allPlayFormat'

/** Every pairing that week: the row team's category W–L–T against each column team. */
export default function HeadToHeadGrid({ teams }: { teams: TeamRow[] }) {
  return (
    <div className="table-wrap h2h-wrap">
      <table>
        <thead>
          <tr>
            <th>Team</th>
            {teams.map((t) => (
              <th key={t.team_key} title={t.name} className="h2h-head">
                {t.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {teams.map((row) => (
            <tr key={row.team_key}>
              <td>{row.name}</td>
              {teams.map((col) => {
                if (col.team_key === row.team_key) return <td key={col.team_key} className="h2h-self">—</td>
                const score = row.all_play?.vs[col.team_key]
                return score ? (
                  <td key={col.team_key} className={`h2h h2h-${tone(score)}`}>{formatWLT(score)}</td>
                ) : (
                  <td key={col.team_key}>–</td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
