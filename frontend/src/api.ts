// Types mirror docs/api.md.
export type Category = { key: string; higher_is_better: boolean; detail_label?: string }
export type StatCell = { value: number | null; rank: number; detail?: string | null }
/** Head-to-head result for a finished week. outcome is null until Yahoo marks the matchup finished. */
export type MatchupResult = {
  outcome: 'W' | 'L' | 'T' | null
  wins: number
  losses: number
  ties: number
  opponent: { team_key: string; name: string }
}
export type TeamRow = {
  team_key: string
  name: string
  avg_rank: number
  /** Optional: browsers may still hold final-week JSON cached before this field existed. */
  median_rank?: number
  place: number
  stats: Record<string, StatCell>
  /** Week responses: the matchup (outcome null while live); null when the team had no matchup or results were unavailable. */
  result?: MatchupResult | null
  /** Current season only: category W–L–T over completed weeks; null when standings were unavailable. */
  record?: { wins: number; losses: number; ties: number } | null
}
export type Rankings = {
  scope: 'week' | 'season'
  week: number | null
  fetched_at: string
  stale: boolean
  refresh_throttled: boolean
  /** Week responses only. Final data ignores refresh. */
  state?: 'current' | 'settling' | 'final'
  categories: Category[]
  teams: TeamRow[]
}
/** The columns a rankings table needs; a finished season carries them too. */
export type RankingsTableData = Pick<Rankings, 'categories' | 'teams'>
export type SeasonRef = { season: number; league_key: string; current: boolean; finished: boolean }
export type SeasonsList = { seasons: SeasonRef[]; complete: boolean }
export type Standing = {
  rank: number | null
  team_key: string
  name: string
  wins: number
  losses: number
  ties: number
  percentage: number | null
  playoff_seed: number | null
}
export type FinalSeason = Omit<Rankings, 'scope' | 'week' | 'state' | 'refresh_throttled'> & {
  season: number
  league_key: string
  standings: Standing[]
}

/** 2025 -> "2025-26". */
export const seasonLabel = (year: number) => `${year}-${String((year + 1) % 100).padStart(2, '0')}`

export type StarPlayer = { rank: number; player_key: string; name: string; nba_team: string; position: string }
export type StarTeam = {
  team_key: string
  name: string
  place: number
  /** Players in the top N, keyed by N ("10", "25", "50"); cumulative. */
  counts: Record<string, number>
  players: StarPlayer[]
}
export type StarPower = {
  /** Set on a finished season's Star Power (/api/stars/<season>). */
  season?: number
  league_key?: string
  fetched_at: string
  stale: boolean
  refresh_throttled: boolean
  levels: number[]
  teams: StarTeam[]
  /** Top-50 players on no team: status is "freeagents", "waivers" (or "team" for an unknown team). */
  unowned: (StarPlayer & { status: string })[]
}

export type League = {
  name: string
  current_week: number
  start_week: number
  end_week: number
  categories: Category[]
}
type Options = { refresh?: boolean }

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function getJson<T>(path: string, opts: Options = {}): Promise<T> {
  const response = await fetch(opts.refresh ? `${path}?refresh=1` : path)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { message?: string }
      if (body.message) message = body.message
    } catch {
      // non-JSON error body; keep the generic message
    }
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

export const getLeague = (opts?: Options) => getJson<League>('/api/league', opts)
export const getSeason = (opts?: Options) => getJson<Rankings>('/api/rankings/season', opts)
export const getWeek = (week: number | 'current' | 'previous', opts?: Options) =>
  getJson<Rankings>(`/api/rankings/week/${week}`, opts)
export const getSeasons = () => getJson<SeasonsList>('/api/seasons')
export const getFinalSeason = (season: number) => getJson<FinalSeason>(`/api/seasons/${season}`)
export const getStars = (opts?: Options) => getJson<StarPower>('/api/stars', opts)
export const getPastStars = (season: number) => getJson<StarPower>(`/api/stars/${season}`)
