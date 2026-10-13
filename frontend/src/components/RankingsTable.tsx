import type { Rankings } from '../api'
import RankCell, { medal } from './RankCell'

export default function RankingsTable({ rankings }: { rankings: Rankings }) {
  const { categories, teams } = rankings
  return (
    <table>
      <thead>
        <tr>
          <th>Team</th>
          <th>Avg Rank</th>
          {categories.flatMap((c) => [
            <th key={c.key}>{c.key}</th>,
            <th key={`${c.key}-rank`}>{c.key} Rk</th>,
            ...(c.detail_label ? [<th key={`${c.key}-detail`}>{c.detail_label}</th>] : []),
          ])}
        </tr>
      </thead>
      <tbody>
        {teams.map((team) => {
          const color = medal(team.place)
          return (
            <tr key={team.name}>
              <td>{team.name}</td>
              <td className={color ? `medal-${color}` : ''}>{team.avg_rank.toFixed(2)}</td>
              {categories.map((c) => (
                <RankCell
                  key={c.key}
                  cell={team.stats[c.key] ?? { value: null, rank: teams.length }}
                  percent={c.key.endsWith('%')}
                  showDetail={Boolean(c.detail_label)}
                />
              ))}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
