import type { Rankings } from '../api'
import RankCell, { medal } from './RankCell'

// Medians of whole-number ranks are whole or end in .5.
const formatMedian = (m?: number) => (m === undefined ? '–' : Number.isInteger(m) ? String(m) : m.toFixed(1))

export default function RankingsTable({ rankings }: { rankings: Rankings }) {
  const { categories, teams } = rankings
  return (
    <table>
      <thead>
        <tr>
          <th>Team</th>
          <th>Avg Rank</th>
          <th>Med Rank</th>
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
            <tr key={team.team_key}>
              <td>{team.name}</td>
              <td className={color ? `medal-${color}` : ''}>{team.avg_rank.toFixed(2)}</td>
              <td>{formatMedian(team.median_rank)}</td>
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
