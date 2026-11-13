import type { ReactNode } from 'react'
import type { RankingsTableData } from '../api'
import RankingsTable from './RankingsTable'

type Props = {
  title: string
  badge?: { text: string; live?: boolean }
  state: { data?: RankingsTableData | null; error?: Error; loading: boolean }
  onRetry: () => void
  actions?: ReactNode
  showLegend?: boolean
  showResult?: boolean
  medals?: boolean
  /** Shown above the rankings table once data has loaded (e.g. a finished season's standings). */
  intro?: ReactNode
  caption?: string
}

const LEGEND = [
  ['gold', '1st in stat'],
  ['silver', '2nd in stat'],
  ['bronze', '3rd in stat'],
] as const

export default function RankingsSection({
  title, badge, state, onRetry, actions, showLegend, showResult, medals, intro, caption,
}: Props) {
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
          {intro}
          {caption && <div className="table-caption">{caption}</div>}
          <div className="scroll-hint">← swipe to see all stats →</div>
          <div className="table-wrap">
            <RankingsTable rankings={state.data} showResult={showResult} medals={medals} />
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
