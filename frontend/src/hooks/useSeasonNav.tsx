import { useState, type ReactNode } from 'react'
import { getSeasons, seasonLabel, type SeasonRef } from '../api'
import ArrowNav from '../components/ArrowNav'
import { useApi } from './useApi'

export type SeasonNav = {
  /** True until the season list has loaded or failed. */
  pending: boolean
  selected: SeasonRef | undefined
  finished: boolean
  /** A past season, or the current one once finished: show the final view, not today's. */
  showFinal: boolean
  /** ‹ › buttons, or undefined with fewer than two seasons. */
  arrows: ReactNode
}

/** The season list plus ‹ › arrows, shared by Full Season and Star Power. 0 = newest. */
export function useSeasonNav(): SeasonNav {
  const list = useApi(() => getSeasons(), [])
  const seasons = list.data?.seasons ?? []
  const [index, setIndex] = useState(0)
  const selected = seasons[index]
  const finished = selected?.finished ?? false
  // Anything but the current season gets its own data, even if Yahoo hasn't flagged it finished;
  // the current season switches to the final view once it is finished (the off-season).
  const showFinal = finished || (selected !== undefined && !selected.current)
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
  return { pending: list.loading && !list.data && !list.error, selected, finished, showFinal, arrows }
}
