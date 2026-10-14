import type { Category, League, Rankings, TeamRow } from '../api'

export const categories: Category[] = [
  { key: 'PTS', higher_is_better: true },
  { key: 'FG%', higher_is_better: true, detail_label: 'FGM/FGA' },
  { key: 'TO', higher_is_better: false },
]

export function team(name: string, place: number, avg = place * 1.0): TeamRow {
  return {
    team_key: `466.l.1.t.${name}`,
    name,
    avg_rank: avg,
    place,
    stats: {
      PTS: { value: 800 - place * 10, rank: place },
      'FG%': { value: 0.482, rank: place, detail: '301/624' },
      TO: { value: 50 + place, rank: place },
    },
  }
}

export function rankings(overrides: Partial<Rankings> = {}): Rankings {
  return {
    scope: 'week',
    week: 7,
    fetched_at: '2026-11-20T18:30:00Z',
    stale: false,
    refresh_throttled: false,
    categories,
    teams: [team('Alpha', 1), team('Beta', 2), team('Gamma', 3), team('Delta', 4)],
    ...overrides,
  }
}

export function league(overrides: Partial<League> = {}): League {
  return { name: "Mutombo's Heavenly Block Party", current_week: 7, start_week: 1, end_week: 21, categories, ...overrides }
}
