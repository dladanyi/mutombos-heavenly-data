import type { StarPlayer, StarPower } from '../api'
import { medal } from './RankCell'

const STATUS = { freeagents: 'FA', waivers: 'W', team: 'other team' } as Record<string, string>
const describe = (p: StarPlayer) => `${p.rank} ${p.name} ${p.nba_team} ${p.position}`
/** 1 for a player within the first (smallest) level, 2 within the second, and so on; levels in any order. */
const tier = (rank: number, levels: number[]) => 1 + levels.filter((level) => rank > level).length

export default function StarPowerTable({ data }: { data: StarPower }) {
  return (
    <>
      <div className="table-wrap star-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Team</th>
              {data.levels.map((level) => (
                <th key={level}>Top {level}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.teams.flatMap((team) => {
              const color = medal(team.place)
              return [
                <tr key={team.team_key} className="star-team">
                  <td className={color ? `medal-${color}` : ''}>{team.place}</td>
                  <td>{team.name}</td>
                  {data.levels.map((level) => (
                    <td key={level}>{team.counts[String(level)] ?? 0}</td>
                  ))}
                </tr>,
                <tr key={`${team.team_key}-players`} className="star-players">
                  <td colSpan={2 + data.levels.length}>
                    {team.players.length === 0
                      ? 'No top-50 players'
                      : team.players.map((p, i) => {
                          // Medal colour by tier; the ★ marks the first tier only.
                          const t = tier(p.rank, data.levels)
                          const color = medal(t)
                          return (
                            <span key={p.player_key}>
                              {i > 0 && ' · '}
                              <span className={color ? `star-player star-${color}` : 'star-player'}>
                                {t === 1 ? `★ ${describe(p)}` : describe(p)}
                              </span>
                            </span>
                          )
                        })}
                  </td>
                </tr>,
              ]
            })}
          </tbody>
        </table>
      </div>
      {data.unowned.length > 0 && (
        <div className="table-caption star-unowned">
          {`Not on a team: ${data.unowned
            .map((p) => `${p.rank} ${p.name}${STATUS[p.status] ? ` (${STATUS[p.status]})` : ''}`)
            .join(' · ')}`}
        </div>
      )}
    </>
  )
}
