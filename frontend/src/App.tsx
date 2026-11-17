import { useEffect, useState } from 'react'
import { getAllPlaySeason, getLeague, getSeason, getWeek } from './api'
import AllPlaySection from './components/AllPlaySection'
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

const tabFromHash = (): Tab =>
  window.location.hash === '#stars' ? 'stars' : window.location.hash === '#allplay' ? 'allplay' : 'rankings'

export default function App() {
  // The screen is chosen by the URL hash (#stars = Star Power, #allplay = All-Play), so it can be
  // bookmarked and Back works.
  const [tab, setTab] = useState<Tab>(tabFromHash)
  // A tab stays mounted once opened (hidden when inactive), so switching back keeps its data and
  // never re-reads an older browser-cached response.
  const [starsOpened, setStarsOpened] = useState(tab === 'stars')
  const [allPlayOpened, setAllPlayOpened] = useState(tab === 'allplay')
  useEffect(() => {
    const onNavigate = () => setTab(tabFromHash())
    window.addEventListener('hashchange', onNavigate)
    window.addEventListener('popstate', onNavigate)
    return () => {
      window.removeEventListener('hashchange', onNavigate)
      window.removeEventListener('popstate', onNavigate)
    }
  }, [])
  if (tab === 'stars' && !starsOpened) setStarsOpened(true) // derived during render, not in an effect
  if (tab === 'allplay' && !allPlayOpened) setAllPlayOpened(true)
  function chooseTab(next: Tab) {
    if (next === tab) return
    if (next === 'stars' || next === 'allplay') window.location.hash = next
    else window.history.pushState(null, '', window.location.pathname + window.location.search) // no bare "#"
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
  // Season all-play loads only once the All-Play tab has been opened.
  const allPlaySeason = useApi(
    (refresh) => (allPlayOpened ? getAllPlaySeason({ refresh }) : Promise.resolve(undefined)),
    [allPlayOpened],
  )

  const [awaitingRefresh, setAwaitingRefresh] = useState(false)
  const [justRefreshed, setJustRefreshed] = useState(false)
  const refreshing =
    league.refreshing || current.refreshing || season.refreshing || past.refreshing || allPlaySeason.refreshing

  async function refreshAll() {
    setJustRefreshed(false)
    const reloads = [league.reload(true), current.reload(true), season.reload(true)]
    if (pastWeek !== undefined) reloads.push(past.reload(true))
    if (allPlayOpened) reloads.push(allPlaySeason.reload(true))
    await Promise.all(reloads)
    setAwaitingRefresh(true)
  }

  const loaded = [current.data, season.data, pastWeek !== undefined ? past.data : undefined].filter(
    (r) => r !== undefined,
  )
  // Final data ignores refresh, so only refreshable rankings decide "Just refreshed".
  const refreshable: { refresh_throttled: boolean }[] = loaded.filter((r) => r.state !== 'final')
  if (allPlaySeason.data) refreshable.push(allPlaySeason.data)
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

  // The week section's title, badge and controls, shared by the Rankings and All-Play tabs.
  const weekTitle = weekNumber ? `Week ${weekNumber}` : 'This Week'
  const weekBadge =
    pastWeek !== undefined
      ? past.data && { text: past.data.state === 'settling' ? 'Settling' : 'Final' }
      : seasonOver
        ? { text: 'Season over' }
        : { text: '● Live', live: true }
  const liveWeek = shown.data?.state === 'current'
  const weekActions = (
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
  )

  return (
    <div className="wrapper">
      {/* The header's time and outage notice describe the rankings; Star Power shows its own. */}
      <Header
        fetchedAt={tab !== 'stars' ? (staleData ?? current.data ?? season.data)?.fetched_at : undefined}
        stale={tab !== 'stars' && Boolean(staleData)}
      />

      <TabBar tab={tab} onChange={chooseTab} />

      {starsOpened && (
        <div hidden={tab !== 'stars'}>
          <StarPowerSection />
        </div>
      )}
      {allPlayOpened && (
        <div hidden={tab !== 'allplay'}>
          <AllPlaySection
            title={weekTitle}
            badge={weekBadge}
            actions={weekActions}
            week={shown}
            live={liveWeek}
            season={allPlaySeason}
          />
        </div>
      )}
      <div hidden={tab !== 'rankings'}>
        <RankingsSection
          title={weekTitle}
          badge={weekBadge}
          state={shown}
          onRetry={() => void shown.reload()}
          showLegend
          showResult
          liveResults={liveWeek}
          actions={weekActions}
        />

        <div className="divider" />

        <FullSeasonSection current={season} onRetry={() => void season.reload()} />
      </div>

      <footer>Mutombo's Heavenly Data &mdash; Fantasy Basketball Intelligence</footer>
    </div>
  )
}
