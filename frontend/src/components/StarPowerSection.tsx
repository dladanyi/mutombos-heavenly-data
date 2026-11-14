import { getStars } from '../api'
import { useApi } from '../hooks/useApi'
import StarPowerTable from './StarPowerTable'

/** The Star Power tab: teams ranked by players in the season-to-date top 10, 25 and 50. */
export default function StarPowerSection() {
  const stars = useApi((refresh) => getStars({ refresh }), [])
  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Star Power</div>
        <span className="section-badge">Season to date · top 50</span>
        <button
          className={stars.refreshing ? 'refresh-btn spinning' : 'refresh-btn'}
          onClick={() => void stars.reload(true)}
          disabled={stars.refreshing}
          title="Refresh"
        >
          Refresh
        </button>
      </div>
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
