import { useEffect, useState } from 'react'
import { getLeague, getSeason, getWeek, type Rankings } from './api'
import Header from './components/Header'
import RankingsSection from './components/RankingsSection'
import { useApi } from './hooks/useApi'

const JUST_REFRESHED_MS = 3000

function RefreshIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13.5 2.5A7 7 0 1 0 14.5 9" />
      <polyline points="14.5,2.5 14.5,6 11,6" />
    </svg>
  )
}

export default function App() {
  const league = useApi((refresh) => getLeague({ refresh }), [])
  const current = useApi((refresh) => getWeek('current', { refresh }), [])
  const season = useApi((refresh) => getSeason({ refresh }), [])

  const info = league.data
  const lastWeek = info && info.current_week > info.start_week ? info.current_week - 1 : undefined
  const last = useApi<Rankings | null>(
    (refresh) => (lastWeek === undefined ? Promise.resolve(null) : getWeek(lastWeek, { refresh })),
    [lastWeek],
  )

  const [awaitingRefresh, setAwaitingRefresh] = useState(false)
  const [justRefreshed, setJustRefreshed] = useState(false)
  const refreshing = league.refreshing || current.refreshing || season.refreshing || last.refreshing

  async function refreshAll() {
    setJustRefreshed(false)
    await Promise.all([league.reload(true), current.reload(true), season.reload(true), last.reload(true)])
    setAwaitingRefresh(true)
  }

  const loaded = [current.data, season.data, last.data].filter((r): r is Rankings => Boolean(r))
  // Final data ignores refresh, so only refreshable rankings decide "Just refreshed".
  const refreshable = loaded.filter((r) => r.state !== 'final')
  const allThrottled = refreshable.length > 0 && refreshable.every((r) => r.refresh_throttled)
  useEffect(() => {
    if (!awaitingRefresh) return
    setAwaitingRefresh(false)
    if (allThrottled) setJustRefreshed(true)
  }, [awaitingRefresh, allThrottled])

  useEffect(() => {
    if (!justRefreshed) return
    const timer = setTimeout(() => setJustRefreshed(false), JUST_REFRESHED_MS)
    return () => clearTimeout(timer)
  }, [justRefreshed])

  const staleData = loaded.find((r) => r.stale)
  const weekNumber = current.data?.week ?? info?.current_week
  // Yahoo leaves current_week on the last week after the season; the backend then reports it ended.
  const seasonOver = Boolean(
    info && current.data?.state && current.data.state !== 'current' && current.data.week === info.end_week,
  )

  return (
    <div className="wrapper">
      <Header fetchedAt={(staleData ?? current.data ?? season.data)?.fetched_at} stale={Boolean(staleData)} />

      <RankingsSection
        title={weekNumber ? `Week ${weekNumber}` : 'This Week'}
        badge={seasonOver ? { text: 'Season over' } : { text: '● Live', live: true }}
        state={current}
        onRetry={() => void current.reload()}
        showLegend
        actions={
          <>
            {justRefreshed && <span className="refresh-note">Just refreshed</span>}
            <button
              className={refreshing ? 'refresh-btn spinning' : 'refresh-btn'}
              onClick={() => void refreshAll()}
              disabled={refreshing}
              title="Refresh"
            >
              <RefreshIcon />
              Refresh
            </button>
          </>
        }
      />

      <div className="divider" />

      <RankingsSection
        title="Full Season"
        badge={{ text: 'Season to date' }}
        state={season}
        onRetry={() => void season.reload()}
      />

      {lastWeek !== undefined && (
        <>
          <div className="divider" />
          <RankingsSection
            title={`Week ${lastWeek}`}
            badge={{ text: 'Last week' }}
            state={last}
            onRetry={() => void last.reload()}
          />
        </>
      )}

      <footer>Mutombo's Heavenly Data &mdash; Fantasy Basketball Intelligence</footer>
    </div>
  )
}
