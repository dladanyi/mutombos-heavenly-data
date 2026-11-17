import type { ReactNode } from 'react'
import type { AllPlaySeason, Rankings } from '../api'
import type { ApiState } from '../hooks/useApi'
import AllPlaySeasonTable from './AllPlaySeasonTable'
import AllPlayTable from './AllPlayTable'
import HeadToHeadGrid from './HeadToHeadGrid'
import { formatTime } from './Header'
import { byAllPlayOrder } from './allPlayFormat'

type Props = {
  title: string
  badge?: { text: string; live?: boolean }
  /** The week arrows and Refresh button, shared with the Rankings tab. */
  actions: ReactNode
  week: ApiState<Rankings | undefined>
  live: boolean
  season: ApiState<AllPlaySeason | undefined>
}

type Loadable = { data?: unknown; error?: Error; loading: boolean; reload: () => Promise<void> }

/** Loading skeleton, error card with retry, or a "Couldn't update" notice above the content. */
function Body({ state, children }: { state: Loadable; children: ReactNode }) {
  if (state.data) {
    return (
      <>
        {state.error && (
          <div className="notice" role="alert">
            Couldn't update: {state.error.message}
          </div>
        )}
        {children}
      </>
    )
  }
  if (state.error && !state.loading) {
    return (
      <div className="error-card" role="alert">
        <span>{state.error.message}</span>
        <button className="refresh-btn" onClick={() => void state.reload()}>
          Try again
        </button>
      </div>
    )
  }
  return <div className="skeleton" aria-label="Loading" />
}

function weeksCaption(s: AllPlaySeason): string {
  if (!s.weeks || s.first_week === null || s.last_week === null) return 'No completed weeks yet'
  return s.first_week === s.last_week ? `Week ${s.first_week}` : `Weeks ${s.first_week}–${s.last_week}`
}

/** The All-Play tab: one week's all-play standings and head-to-head grid, then the season. */
export default function AllPlaySection({ title, badge, actions, week, live, season }: Props) {
  const teams = week.data ? byAllPlayOrder(week.data.teams) : []
  return (
    <>
      <div className="section">
        <div className="section-header">
          <div className="section-title">{title}</div>
          {badge && <span className={badge.live ? 'section-badge live' : 'section-badge'}>{badge.text}</span>}
          {actions}
        </div>
        <Body state={week}>
          {teams.length === 0 && week.data?.teams.length ? (
            <div className="notice" role="status">
              Tap Refresh to see all-play numbers
            </div>
          ) : (
            <>
              <AllPlayTable teams={teams} live={live} />
              <div className="section-header">
                <div className="section-title">Head-to-head</div>
              </div>
              <div className="table-caption">Row team's category W–L–T vs each column team</div>
              <HeadToHeadGrid teams={teams} />
            </>
          )}
        </Body>
      </div>

      <div className="divider" />

      <div className="section">
        <div className="section-header">
          <div className="section-title">Season All-Play</div>
        </div>
        <Body state={season}>
          {season.data && (
            <>
              <div className="table-caption">{weeksCaption(season.data)}</div>
              {season.data.stale && (
                <div className="notice" role="status">
                  Showing data as of {formatTime(season.data.fetched_at)} (Yahoo unavailable)
                </div>
              )}
              {season.data.teams.length > 0 && <AllPlaySeasonTable data={season.data} />}
            </>
          )}
        </Body>
      </div>
    </>
  )
}
