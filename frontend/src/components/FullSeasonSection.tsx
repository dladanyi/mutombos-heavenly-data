import { getFinalSeason, type Rankings } from '../api'
import type { ApiState } from '../hooks/useApi'
import { useApi } from '../hooks/useApi'
import { useSeasonNav } from '../hooks/useSeasonNav'
import RankingsSection from './RankingsSection'
import StandingsTable from './StandingsTable'

type Props = { current: ApiState<Rankings>; onRetry: () => void }

/** Full Season with ‹ › arrows: today's view while a season is in progress, the final view once finished. */
export default function FullSeasonSection({ current, onRetry }: Props) {
  const { selected, finished, showFinal, arrows } = useSeasonNav()
  const year = selected?.season
  const final = useApi(
    () => (showFinal && year !== undefined ? getFinalSeason(year) : Promise.resolve(undefined)),
    [year, showFinal],
  )

  if (!showFinal) {
    return (
      <RankingsSection
        title="Full Season"
        badge={{ text: 'Season to date' }}
        state={current}
        onRetry={onRetry}
        actions={arrows}
        showRecord
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
