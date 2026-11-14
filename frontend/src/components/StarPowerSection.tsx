import { getPastStars, getStars } from '../api'
import { useApi } from '../hooks/useApi'
import { useSeasonNav } from '../hooks/useSeasonNav'
import { formatTime } from './Header'
import StarPowerTable from './StarPowerTable'

/** The Star Power tab: teams ranked by players in the top 10, 25 and 50, with ‹ › for past seasons. */
export default function StarPowerSection() {
  const { pending, selected, finished, showFinal, arrows } = useSeasonNav()
  // Wait for the season list before fetching: in the off-season the current season is shown
  // final, and fetching today's view first would cost a wasted Yahoo call and a visible flip.
  const target = pending ? 'pending' : showFinal ? selected?.season ?? 'current' : 'current'
  const stars = useApi(
    (refresh) =>
      target === 'pending'
        ? new Promise<never>(() => {}) // stays loading; replaced once the list arrives
        : target === 'current'
          ? getStars({ refresh })
          : getPastStars(target),
    [target],
  )

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Star Power</div>
        <span className="section-badge">
          {showFinal ? (finished ? 'Final' : 'Past season') : 'Season to date'} · top 50
        </span>
        {arrows}
        {!showFinal && (
          <button
            className={stars.refreshing ? 'refresh-btn spinning' : 'refresh-btn'}
            onClick={() => void stars.reload(true)}
            disabled={stars.refreshing}
            title="Refresh"
          >
            Refresh
          </button>
        )}
      </div>
      {stars.data && (
        <div className="table-caption">
          {finished ? 'Full-season ranks · rosters at season end' : `As of ${formatTime(stars.data.fetched_at)}`}
        </div>
      )}
      {stars.data?.stale && (
        <div className="notice" role="status">
          Showing data as of {formatTime(stars.data.fetched_at)} (Yahoo unavailable)
        </div>
      )}
      {stars.data && stars.error && (
        <div className="notice" role="alert">
          Couldn't update: {stars.error.message}
        </div>
      )}
      {stars.data ? (
        <StarPowerTable data={stars.data} />
      ) : stars.error && !stars.loading ? (
        <div className="error-card" role="alert">
          <span>{stars.error.message}</span>
          <button className="refresh-btn" onClick={() => void stars.reload()}>
            Try again
          </button>
        </div>
      ) : (
        <div className="skeleton" aria-label="Loading" />
      )}
    </div>
  )
}
