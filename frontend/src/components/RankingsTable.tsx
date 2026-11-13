import type { MatchupResult, RankingsTableData } from '../api'
import RankCell, { medal } from './RankCell'

// Medians of whole-number ranks are whole or end in .5, so String() is enough ('3', '2.5').
const formatMedian = (m?: number | null) => (m == null ? '–' : String(m))

function ResultCell({ result, live }: { result?: MatchupResult | null; live?: boolean }) {
  if (!result) return <td className="result-cell">–</td>
  const score = [result.wins, result.losses, ...(result.ties ? [result.ties] : [])].join('–')
  const outcome = result.outcome ?? ''
  // A live matchup is coloured by who is leading so far (neutral before any category is decided);
  // a finished week without an outcome from Yahoo stays neutral rather than looking decided.
  const decided = result.wins + result.losses + result.ties > 0
  const tone = outcome || (live && decided ? (result.wins > result.losses ? 'W' : result.wins < result.losses ? 'L' : 'T') : '')
  return (
    <td className="result-cell">
      <span className={tone ? `result result-${tone.toLowerCase()}` : 'result'}>{outcome ? `${outcome} ${score}` : score}</span>{' '}
      <span className="result-opp">vs {result.opponent.name}</span>
    </td>
  )
}

type Props = {
  rankings: RankingsTableData
  showResult?: boolean
  /** The week is in progress: the column is headed "Matchup" and coloured by who is leading. */
  liveResults?: boolean
  showRecord?: boolean
  /** Colour Avg Rank by place. Off for finished seasons, whose standings carry the medals. */
  medals?: boolean
}

export default function RankingsTable({ rankings, showResult, liveResults, showRecord, medals = true }: Props) {
  const { categories, teams } = rankings
  return (
    <table>
      <thead>
        <tr>
          <th>Team</th>
          {showResult && <th className="result-cell">{liveResults ? 'Matchup' : 'Result'}</th>}
          {showRecord && <th>Record</th>}
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
          const color = medals ? medal(team.place) : undefined
          return (
            <tr key={team.team_key}>
              <td>{team.name}</td>
              {showResult && <ResultCell result={team.result} live={liveResults} />}
              {showRecord && (
                <td>{team.record ? `${team.record.wins}–${team.record.losses}–${team.record.ties}` : '–'}</td>
              )}
              <td className={color ? `avg-rank medal-${color}` : 'avg-rank'}>{team.avg_rank.toFixed(2)}</td>
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
