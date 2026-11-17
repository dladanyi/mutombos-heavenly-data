/** What each All-Play column heading means, keyed by heading label. Copy: docs/specs/2026-11-16-column-help-design.md */

export const WEEK_HELP: Record<string, string> = {
  'Avg Cats':
    'Categories this team would win, on average, against each other team this week, out of 9. Ties count half.',
  'All-Play':
    "This team's record if it had played every other team this week (wins–losses–ties). Winning more categories than the other team counts as a win.",
  'Win %': 'Share of those all-play games won, with ties counting half.',
}

export const SEASON_HELP: Record<string, string> = {
  'All-Play': 'Weekly all-play records added up over every completed week.',
  'Win %': 'Share of all-play games won this season, with ties counting half. The table is ranked by this.',
  'Avg Cats': 'The weekly Avg Cats averaged over the completed weeks.',
  Record: "The team's real category record (wins–losses–ties) from its actual matchups in the same weeks.",
  Luck: 'Real categories won minus Avg Cats, averaged per week. Above zero means the team met weaker opponents than the league average; below zero means tougher ones.',
}
