import type { ReactNode } from 'react'
import type { Rankings } from '../api'
import RankingsTable from './RankingsTable'

type Props = {
  title: string
  badge?: { text: string; live?: boolean }
  state: { data?: Rankings | null; error?: Error; loading: boolean }
  onRetry: () => void
  actions?: ReactNode
  showLegend?: boolean
}

const LEGEND = [
  ['gold', '1st in stat'],
  ['silver', '2nd in stat'],
  ['bronze', '3rd in stat'],
] as const

export default function RankingsSection({ title, badge, state, onRetry, actions, showLegend }: Props) {
  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">{title}</div>
        {badge && <span className={badge.live ? 'section-badge live' : 'section-badge'}>{badge.text}</span>}
        {actions}
      </div>
      {showLegend && (
        <div className="legend">
          {LEGEND.map(([color, label]) => (
            <div className="legend-item" key={color}>
              <div
                className="legend-swatch"
                style={{ background: `var(--${color}-bg)`, border: `1px solid var(--${color})` }}
              />
              {label}
            </div>
          ))}
        </div>
      )}
      {state.data && state.error && (
        <div className="notice" role="alert">
          Couldn't update: {state.error.message}
        </div>
      )}
      {state.data ? (
        <>
          <div className="scroll-hint">← swipe to see all stats →</div>
          <div className="table-wrap">
            <RankingsTable rankings={state.data} />
          </div>
        </>
      ) : state.error && !state.loading ? (
        <div className="error-card" role="alert">
          <span>{state.error.message}</span>
          <button className="refresh-btn" onClick={onRetry}>
            Try again
          </button>
        </div>
      ) : (
        <div className="skeleton" aria-label="Loading" />
      )}
    </div>
  )
}
