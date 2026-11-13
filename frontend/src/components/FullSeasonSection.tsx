import { useState } from 'react'
import { getFinalSeason, getSeasons, seasonLabel, type Rankings } from '../api'
import type { ApiState } from '../hooks/useApi'
import { useApi } from '../hooks/useApi'
import RankingsSection from './RankingsSection'
import StandingsTable from './StandingsTable'

type Props = { current: ApiState<Rankings>; onRetry: () => void }

/** Full Season with ‹ › arrows: today's view while a season is in progress, the final view once finished. */
export default function FullSeasonSection({ current, onRetry }: Props) {
  const list = useApi(() => getSeasons(), [])
  const seasons = list.data?.seasons ?? []
  const [index, setIndex] = useState(0) // 0 = newest
  const selected = seasons[index]
  const finished = selected?.finished ?? false
  // Anything but the current season gets its own data, even if Yahoo hasn't flagged it finished;
  // the current season switches to the final view once it is finished (the off-season).
  const showFinal = finished || (selected !== undefined && !selected.current)
  const year = selected?.season
  const final = useApi(
    () => (showFinal && year !== undefined ? getFinalSeason(year) : Promise.resolve(undefined)),
    [year, showFinal],
  )

  const arrows =
    seasons.length > 1 && year !== undefined ? (
      <div className="season-nav">
        <button
          className="refresh-btn season-arrow"
          aria-label="Previous season"
          disabled={index >= seasons.length - 1}
          onClick={() => setIndex(index + 1)}
        >
          ‹
        </button>
        <span className="season-label">{seasonLabel(year)}</span>
        <button
          className="refresh-btn season-arrow"
          aria-label="Next season"
          disabled={index === 0}
          onClick={() => setIndex(index - 1)}
        >
          ›
        </button>
      </div>
    ) : undefined

  if (!showFinal) {
    return (
      <RankingsSection
        title="Full Season"
        badge={{ text: 'Season to date' }}
        state={current}
        onRetry={onRetry}
        actions={arrows}
      />
    )
  }
  return (
    <RankingsSection
      title="Full Season"
      badge={{ text: finished ? 'Final' : 'Past season' }}
      state={final}
      onRetry={() => void final.reload()}
      actions={arrows}
      medals={false}
      intro={final.data && <StandingsTable standings={final.data.standings} rankings={final.data} />}
      caption="Season totals, including playoffs"
    />
  )
}
