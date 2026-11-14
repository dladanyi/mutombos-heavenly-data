import type { Category, FinalSeason, League, Rankings, SeasonsList, Standing, StarPower, TeamRow } from '../api'

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
    median_rank: place,
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

export function standing(rank: number | null, name: string, overrides: Partial<Standing> = {}): Standing {
  return { rank, team_key: `466.l.1.t.${name}`, name, wins: 100, losses: 78, ties: 2, percentage: 0.561, playoff_seed: rank, ...overrides }
}

export function seasonsList(overrides: Partial<SeasonsList> = {}): SeasonsList {
  return {
    seasons: [
      { season: 2026, league_key: '478.l.1', current: true, finished: false },
      { season: 2025, league_key: '466.l.1', current: false, finished: true },
    ],
    complete: true,
    ...overrides,
  }
}

export function finalSeason(overrides: Partial<FinalSeason> = {}): FinalSeason {
  return {
    season: 2025,
    league_key: '466.l.1',
    fetched_at: '2026-04-10T18:30:00Z',
    stale: false,
    categories,
    standings: [
      standing(1, 'Team 4', { wins: 118, losses: 60, ties: 2, percentage: 0.661, playoff_seed: 1 }),
      standing(2, 'Team 3', { playoff_seed: 3 }),
      standing(3, 'Team 9', { playoff_seed: 4 }),
      standing(4, 'Team 10', { playoff_seed: null }),
    ],
    teams: [team('Team 4', 1), team('Team 3', 2), team('Team 9', 3)],
    ...overrides,
  }
}

const star = (rank: number, name: string, nba_team = 'SAS', position = 'C') => ({ rank, player_key: `p.${rank}`, name, nba_team, position })

export function starPower(overrides: Partial<StarPower> = {}): StarPower {
  return {
    fetched_at: '2026-11-20T18:30:00Z',
    stale: false,
    refresh_throttled: false,
    levels: [10, 25, 50],
    teams: [
      { team_key: 't.1', name: 'Alpha', place: 1, counts: { '10': 2, '25': 3, '50': 4 },
        players: [star(1, 'Victor Wembanyama'), star(8, 'Player Eight'), star(14, 'Player Fourteen'), star(31, 'Player ThirtyOne')] },
      { team_key: 't.2', name: 'Beta', place: 2, counts: { '10': 1, '25': 1, '50': 1 }, players: [star(3, 'Player Three')] },
      { team_key: 't.3', name: 'Gamma', place: 3, counts: { '10': 0, '25': 0, '50': 1 }, players: [star(40, 'Player Forty')] },
      { team_key: 't.4', name: 'Delta', place: 4, counts: { '10': 0, '25': 0, '50': 0 }, players: [] },
    ],
    unowned: [{ ...star(37, 'Player X'), status: 'freeagents' }, { ...star(48, 'Player Y'), status: 'waivers' }],
    ...overrides,
  }
}
