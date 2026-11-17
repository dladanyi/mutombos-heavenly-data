import type { TeamRow, WLT } from '../api'

/** 9–1–0 (ties always shown). */
export const formatWLT = (r: WLT) => `${r.wins}–${r.losses}–${r.ties}`

/** .900, 1.000, .000 */
export const formatPct = (p: number) => p.toFixed(3).replace(/^0/, '')

/** +0.25, −0.75 (a real minus sign), 0.00; – when missing. */
export function formatLuck(luck: number | null): string {
  if (luck === null) return '–'
  const text = Math.abs(luck).toFixed(2)
  if (text === '0.00') return text
  return luck > 0 ? `+${text}` : `−${text}`
}

/** Teams that carry all-play numbers, in the server's all-play order. */
export const byAllPlayOrder = (teams: TeamRow[]) =>
  teams.filter((t) => t.all_play).sort((a, b) => a.all_play!.order - b.all_play!.order)

/** w / l / t tone for a W–L–T, from the first team's side. */
export const tone = (r: WLT) => (r.wins > r.losses ? 'w' : r.wins < r.losses ? 'l' : 't')
