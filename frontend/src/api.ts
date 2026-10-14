// Types mirror docs/api.md.
export type Category = { key: string; higher_is_better: boolean; detail_label?: string }
export type StatCell = { value: number | null; rank: number; detail?: string | null }
export type TeamRow = { team_key: string; name: string; avg_rank: number; place: number; stats: Record<string, StatCell> }
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
