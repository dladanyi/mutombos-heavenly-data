import { useEffect, useState } from 'react'
import { getLeague, getSeason, getWeek } from './api'
import ArrowNav from './components/ArrowNav'
import Header from './components/Header'
import FullSeasonSection from './components/FullSeasonSection'
import RankingsSection from './components/RankingsSection'
import StarPowerSection from './components/StarPowerSection'
import TabBar, { type Tab } from './components/TabBar'
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

const tabFromHash = (): Tab => (window.location.hash === '#stars' ? 'stars' : 'rankings')

export default function App() {
  // The screen is chosen by the URL hash (#stars = Star Power), so it can be bookmarked and Back works.
  const [tab, setTab] = useState<Tab>(tabFromHash)
  useEffect(() => {
    const onHash = () => setTab(tabFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  function chooseTab(next: Tab) {
    window.location.hash = next === 'stars' ? 'stars' : ''
    setTab(next)
  }

  const league = useApi((refresh) => getLeague({ refresh }), [])
  const current = useApi((refresh) => getWeek('current', { refresh }), [])
  const season = useApi((refresh) => getSeason({ refresh }), [])

  const info = league.data
  // The week chosen with the arrows (null = the live week). A week number, not an offset, so the
  // table doesn't change under the user when Yahoo rolls over to a new week.
  const [chosenWeek, setChosenWeek] = useState<number | null>(null)
  const pastWeek =
    info && chosenWeek !== null && chosenWeek < info.current_week ? Math.max(chosenWeek, info.start_week) : undefined
  const past = useApi(
    (refresh) => (pastWeek !== undefined ? getWeek(pastWeek, { refresh }) : Promise.resolve(undefined)),
    [pastWeek],
  )
  const shown = pastWeek !== undefined ? past : current

  const [awaitingRefresh, setAwaitingRefresh] = useState(false)
  const [justRefreshed, setJustRefreshed] = useState(false)
  const refreshing = league.refreshing || current.refreshing || season.refreshing || past.refreshing

  async function refreshAll() {
    setJustRefreshed(false)
    const reloads = [league.reload(true), current.reload(true), season.reload(true)]
    if (pastWeek !== undefined) reloads.push(past.reload(true))
    await Promise.all(reloads)
    setAwaitingRefresh(true)
  }

  const loaded = [current.data, season.data, pastWeek !== undefined ? past.data : undefined].filter(
    (r) => r !== undefined,
  )
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
  const weekNumber = pastWeek ?? current.data?.week ?? info?.current_week
  // Yahoo leaves current_week on the last week after the season; the backend then reports it ended.
  const seasonOver = Boolean(
    info && current.data?.state && current.data.state !== 'current' && current.data.week === info.end_week,
  )

  return (
    <div className="wrapper">
      <Header fetchedAt={(staleData ?? current.data ?? season.data)?.fetched_at} stale={Boolean(staleData)} />

      <TabBar tab={tab} onChange={chooseTab} />

      {tab === 'stars' ? (
        <StarPowerSection />
      ) : (
        <>
          <RankingsSection
            title={weekNumber ? `Week ${weekNumber}` : 'This Week'}
            badge={
              pastWeek !== undefined
                ? past.data && { text: past.data.state === 'settling' ? 'Settling' : 'Final' }
                : seasonOver
                  ? { text: 'Season over' }
                  : { text: '● Live', live: true }
            }
            state={shown}
            onRetry={() => void shown.reload()}
            showLegend
            showResult
            liveResults={shown.data?.state === 'current'}
            actions={
              <>
                {info && info.current_week > info.start_week && (
                  <ArrowNav
                    backLabel="Previous week"
                    forwardLabel="Next week"
                    canBack={(pastWeek ?? info.current_week) > info.start_week}
                    canForward={pastWeek !== undefined}
                    onBack={() => setChosenWeek((pastWeek ?? info.current_week) - 1)}
                    onForward={() => setChosenWeek(pastWeek !== undefined && pastWeek + 1 < info.current_week ? pastWeek + 1 : null)}
                  />
                )}
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

          <FullSeasonSection current={season} onRetry={() => void season.reload()} />
        </>
      )}

      <footer>Mutombo's Heavenly Data &mdash; Fantasy Basketball Intelligence</footer>
    </div>
  )
}
