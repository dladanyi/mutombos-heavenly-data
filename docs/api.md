# API reference

> **Status:** implemented on branch `stability-refactor` (2026-10-12); not yet deployed.

All endpoints return JSON.

## Endpoints

| Method + path | Description |
|---|---|
| `GET /api/league` | League metadata |
| `GET /api/rankings/season` | Season-to-date rankings |
| `GET /api/rankings/week/current` | Current week rankings |
| `GET /api/rankings/week/previous` | Last week's rankings; 404 in the league's first week |
| `GET /api/rankings/week/<n>` | Rankings for week `n` |
| `GET /api/seasons` | Seasons this Yahoo account can read, newest first |
| `GET /api/seasons/<season>` | A finished season: final standings plus whole-season rankings |
| `GET /healthz` | Returns `ok`; never calls Yahoo. If a required env var is missing the function can't start, so this returns Vercel's own 500 |

## Caching headers

| Data | `Cache-Control` | `Vercel-CDN-Cache-Control` |
|---|---|---|
| League, season, current week, and `/week/current` and `/week/previous` in any state | `public, max-age=60` | `max-age=60` |
| Week that ended less than 3 days ago | `public, max-age=300` | `max-age=3600` |
| Final week (ended 3+ days ago), by number only | `public, max-age=86400` | `max-age=31536000` |
| `/api/seasons` | `public, max-age=60` | `max-age=60` |
| `/api/seasons/<season>`, finished and fetched as final | `public, max-age=86400` | `max-age=31536000` |
| `?refresh=1`, `/healthz`, errors, stale responses, an incomplete season list | `no-store` | `no-store` |

Adding `?refresh=1` to any `/api` endpoint skips the server cache (at most once every 30 s per
resource).

## `GET /api/league`

```json
{
  "name": "Mutombo's Heavenly Block Party",
  "current_week": 7,
  "start_week": 1,
  "end_week": 21,
  "categories": [{"key": "PTS", "higher_is_better": true}]
}
```

## Rankings response

```json
{
  "scope": "week",
  "week": 7,
  "fetched_at": "2026-10-13T05:41:00Z",
  "stale": false,
  "refresh_throttled": false,
  "state": "current",
  "categories": [
    {"key": "FG%", "higher_is_better": true, "detail_label": "FGM/FGA"}
  ],
  "teams": [
    {
      "team_key": "466.l.46425.t.1",
      "name": "Team A",
      "avg_rank": 2.89,
      "median_rank": 3.0,
      "place": 1,
      "stats": {"FG%": {"value": 0.482, "rank": 3, "detail": "301/624"}},
      "result": {"outcome": "W", "wins": 5, "losses": 3, "ties": 1,
                 "opponent": {"team_key": "466.l.46425.t.4", "name": "Team D"}}
    }
  ]
}
```

- `scope` is `"week"` or `"season"`. `week` is `null` for the season.
- `fetched_at` is when the data was fetched from Yahoo (UTC).
- `stale` is `true` when Yahoo failed and cached data is being returned.
- `refresh_throttled` is `true` when `?refresh=1` was ignored because the data was refreshed
  less than 30 s ago. Final data ignores `?refresh=1` and always reports `false`.
- `state` (week responses only) is `"current"`, `"settling"` (up to 3 days after the week's
  end date) or `"final"`. After the season, the last week moves to settling and final by its
  calendar date even though Yahoo still calls it the current week.
- `team_key` is Yahoo's unique team ID. Use it, not `name`, to identify a team.
- Categories, in order: PTS, REB, AST, ST, BLK, 3PTM, FG%, FT%, TO. Only TO is lower-is-better.
- `value` is `null` if Yahoo has no value yet. Such teams get the worst rank in that category.
- Ranks use the "min" tie method (ties share the best rank). `place` is the team's position by
  `avg_rank`, using the same tie method.
- `avg_rank` is the mean of the category ranks (2 decimals). `median_rank` is their median.
  With 9 categories that is always a whole number; it's sent as a float. `median_rank` is
  informational only: sorting and `place` still use `avg_rank`. Browsers may hold final-week
  responses cached before `median_rank` existed for up to a day (the CDN cache is per
  deployment, so it starts empty), so clients treat it as optional.
- `record` (season response only) is the team's category W–L–T from Yahoo's standings, over
  completed weeks: `{"wins": 17, "losses": 10, "ties": 0}`. It's `null` for a team missing from
  the standings, and for every team when the standings couldn't be fetched (that response is
  sent `no-store`).
- `result` (week responses) is the team's head-to-head matchup that week, from Yahoo's
  scoreboard. `wins`/`losses`/`ties` count categories from this team's side. `outcome` is
  `"W"`, `"L"` or `"T"` once Yahoo marks the matchup finished, and `null` while it's in
  progress (the current week: categories won so far, refreshed with the week's 5-minute
  cache). `result` is `null` for a team with no matchup (e.g. a playoff bye) and for every
  team when the scoreboard couldn't be fetched; that response is sent `no-store` so the gap
  isn't cached. A final week only gets the long CDN cache when both its stats and its
  scoreboard were fetched as final.

## `GET /api/seasons`

```json
{"seasons": [
  {"season": 2026, "league_key": "478.l.46425", "current": true, "finished": false},
  {"season": 2025, "league_key": "466.l.11070", "current": false, "finished": true}
], "complete": true}
```

- Found by following each league's `renew` link (previous season's league) from the configured
  league. The walk ends at a league with no `renew`, or at one Yahoo answers with HTTP 403
  (this account wasn't in it; 2024-25 today). That stop is remembered for a day.
- `complete: false` means a Yahoo outage cut the walk short, so older seasons may be missing.
- `season` is the year the season starts (2025 = "2025-26").

## `GET /api/seasons/<season>`

For finished seasons only: any past season, and the current one once Yahoo marks it finished
(the off-season). 404 for the in-progress current season (use `/api/rankings/season`) and for
a season that isn't in the list. 503 if the season isn't found while the list is incomplete.

```json
{
  "season": 2025,
  "league_key": "466.l.11070",
  "fetched_at": "2026-11-13T21:40:00Z",
  "stale": false,
  "categories": [{"key": "PTS", "higher_is_better": true}],
  "standings": [
    {"rank": 1, "team_key": "466.l.11070.t.4", "name": "Team A", "wins": 118, "losses": 60,
     "ties": 2, "percentage": 0.661, "playoff_seed": 1}
  ],
  "teams": [{"team_key": "466.l.11070.t.4", "name": "Team A", "avg_rank": 2.78, "...": "..."}]
}
```

- `standings` is sorted by `rank`, the final finish after the playoffs (not regular-season
  order). `rank` and `playoff_seed` can be `null` when Yahoo leaves them blank.
- `wins`/`losses`/`ties` count categories over the **regular season**.
- `teams` has the same rows as the rankings response, computed from Yahoo's **whole-season
  totals, playoff weeks included**.

## Errors

| Status | Body |
|---|---|
| 404 | `{"error": "not_found"}`, including a week outside `start_week..current_week` and an unknown or in-progress season |
| 503 | `{"error": "yahoo_unavailable", "message": "..."}`, when Yahoo failed and nothing is cached |
| 500 | `{"error": "internal", "message": "..."}` |
