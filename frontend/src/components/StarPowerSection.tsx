import { useState } from 'react'
import { getPastStars, getSeasons, getStars, seasonLabel } from '../api'
import { useApi } from '../hooks/useApi'
import ArrowNav from './ArrowNav'
import { formatTime } from './Header'
import StarPowerTable from './StarPowerTable'

/** The Star Power tab: teams ranked by players in the top 10, 25 and 50, with ‹ › for past seasons. */
export default function StarPowerSection() {
  const list = useApi(() => getSeasons(), [])
  const seasons = list.data?.seasons ?? []
  const [index, setIndex] = useState(0) // 0 = newest
  const selected = seasons[index]
  const finished = selected?.finished ?? false
  // Same rule as Full Season: a past season, or the current one once finished, shows the final
  // view (full-season ranks, end-of-season rosters). Until the list loads, show today's view.
  const showFinal = finished || (selected !== undefined && !selected.current)
  const year = showFinal ? selected?.season : undefined
  const stars = useApi(
    (refresh) => (year !== undefined ? getPastStars(year) : getStars({ refresh })),
    [year],
  )

  const arrows =
    seasons.length > 1 && selected ? (
      <ArrowNav
        label={seasonLabel(selected.season)}
        backLabel="Previous season"
        forwardLabel="Next season"
        canBack={index < seasons.length - 1}
        canForward={index > 0}
        onBack={() => setIndex(index + 1)}
        onForward={() => setIndex(index - 1)}
      />
    ) : undefined

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
          {showFinal ? 'Full-season ranks · rosters at season end' : `As of ${formatTime(stars.data.fetched_at)}`}
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
