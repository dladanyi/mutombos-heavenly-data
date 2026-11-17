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
| `GET /api/stars` | Star Power: teams ranked by players in the season-to-date top 10/25/50 |
| `GET /api/stars/<season>` | A finished season's Star Power: final full-season ranks, end-of-season rosters |
| `GET /api/allplay/season` | Season all-play: weekly all-play summed over the current season's completed weeks, with real Record and Luck |
| `GET /healthz` | Returns `ok`; never calls Yahoo. If a required env var is missing the function can't start, so this returns Vercel's own 500 |

## Caching headers

| Data | `Cache-Control` | `Vercel-CDN-Cache-Control` |
|---|---|---|
| League, season, current week, and `/week/current` and `/week/previous` in any state | `public, max-age=60` | `max-age=60` |
| Week that ended less than 3 days ago | `public, max-age=300` | `max-age=3600` |
| Final week (ended 3+ days ago), by number only | `public, max-age=86400` | `max-age=31536000` |
| `/api/seasons` | `public, max-age=60` | `max-age=60` |
| `/api/stars` | `public, max-age=300` | `max-age=3600` |
| `/api/seasons/<season>` and `/api/stars/<season>`, finished and fetched as final | `public, max-age=86400` | `max-age=31536000` |
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
                 "opponent": {"team_key": "466.l.46425.t.4", "name": "Team D"}},
      "all_play": {"avg_cats": 5.67, "wins": 9, "losses": 1, "ties": 0, "pct": 0.9,
                   "place": 1, "order": 1,
                   "vs": {"466.l.46425.t.4": {"wins": 6, "losses": 3, "ties": 0}}}
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
- `all_play` (week responses only) plays this team against every other team that week, using
  the week's totals. Per category the higher value wins (lower for TO), equal values tie, a
  value beats a missing one and two missing values tie. `vs` holds the category W–L–T against
  each opponent, keyed by `team_key`, from this team's side. A matchup is a W when the team
  took more categories than it lost, T when equal. `wins`/`losses`/`ties` count those all-play
  matchups. `avg_cats` is categories won (ties count half) per opponent, 2 decimals; `pct` is
  `(wins + ties/2) / opponents`, 3 decimals. All-play order is `avg_cats`, then `pct` (both
  descending), then name; `order` is the 1-based position in it, and `place` is 1 + the number
  of teams with a higher `avg_cats` (ties share a place). The `teams` list itself stays in avg
  rank order. Clients treat `all_play` as optional: browsers may hold final-week responses
  cached before it existed for up to a day.

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

## `GET /api/stars`

```json
{
  "fetched_at": "2026-11-13T21:40:00Z", "stale": false, "refresh_throttled": false,
  "levels": [10, 25, 50],
  "teams": [
    {"team_key": "478.l.46425.t.7", "name": "Team A", "place": 1,
     "counts": {"10": 3, "25": 4, "50": 5},
     "players": [{"rank": 2, "player_key": "466.p.6014", "name": "Luka Dončić",
                  "nba_team": "LAL", "position": "PG,SG"}]}
  ],
  "unowned": [{"rank": 37, "player_key": "...", "name": "...", "nba_team": "...",
               "position": "...", "status": "freeagents"}]
}
```

- Rankings are Yahoo's season-to-date "actual rank" in this league's categories
  (`players;sort=AR;sort_type=season`), top 50, fetched in two pages of 25. `rank` is the
  position in that order.
- `counts` are cumulative (the top 25 includes the top 10). Teams are ordered by top-10 count,
  then top 25, then top 50, then name. `place` is shared on ties.
- Every team is listed, including teams with no top-50 players.
- `unowned` lists top-50 players on no team: `freeagents`, `waivers`, or `team` for an owner the
  league's team list doesn't have.
- Cached 1 hour on the server and the CDN (Yahoo updates season ranks about daily).

## `GET /api/stars/<season>`

The same body as `/api/stars`, plus `"season": 2025` and `"league_key": "466.l.11070"`, for a
finished season: any past season, or the current one once Yahoo marks it finished.

- For a past league Yahoo returns the **final full-season ranks** and **end-of-season
  ownership**, so a player traded mid-season counts for the team that finished with him.
- `season` is matched the same way as `/api/seasons/<season>`: 404 for the in-progress season,
  an unknown season or bad input, and 503 if an outage cut the season list short.
- A finished season is cached forever on the server, with final headers once both the players
  and the team list are final. Otherwise the 1-hour Star Power headers apply.

## `GET /api/allplay/season`

```json
{
  "scope": "allplay-season",
  "fetched_at": "2026-11-16T05:41:00Z", "stale": false, "refresh_throttled": false,
  "weeks": 4, "first_week": 1, "last_week": 4,
  "teams": [
    {"team_key": "466.l.11070.t.3", "name": "Team C", "place": 1,
     "wins": 31, "losses": 7, "ties": 2, "pct": 0.8, "avg_cats": 5.41, "weeks": 4,
     "record": {"wins": 22, "losses": 13, "ties": 1}, "luck": -0.21}
  ]
}
```

- **Weeks counted:** `start_week` to `current_week − 1`, plus the current week once its state
  is no longer `"current"` (after the season). The live week never counts. Playoff and
  consolation weeks count once played. Before any week has finished: `weeks: 0`,
  `first_week`/`last_week` `null`, `teams: []`.
- Each week is scored exactly like the week response's `all_play`. `wins`/`losses`/`ties` sum
  the weekly all-play matchups; `pct` is `(wins + ties/2) / matchups`, 3 decimals; `avg_cats`
  is the mean of the team's weekly Avg Cats over the `weeks` it appears in, 2 decimals.
- Order: `pct`, then `avg_cats` (both descending), then name. `place` is 1 + the number of
  teams with a higher `pct`.
- `record` is the team's real category W–L–T summed from each counted week's scoreboard (not
  Yahoo's standings, which stop at the regular season). `luck` is the mean, over weeks with a
  real matchup, of real categories won (ties count half) minus that week's Avg Cats, 2
  decimals; positive means the team has won more categories than its all-play strength
  predicts. Weeks without a matchup (bye) count toward all-play but not `record` or `luck`.
  Both are `null` for a team with no matchup in any counted week, and for every team when any
  counted week's scoreboard couldn't be fetched (that response is sent `no-store`).
- The week stats and scoreboards come through the same cache as the week route (final weeks
  are kept forever), so a cold instance makes about two Yahoo calls per counted week, up to
  6 weeks at a time.
- `fetched_at` is the oldest input's fetch time. `stale` is true when any input is stale,
  including the league lookup that decides which weeks count.
  `refresh_throttled` is true on `?refresh=1` when every non-final input reported a throttled
  refresh, including when every input is final (final data ignores refresh).
- A counted week whose stats can't be fetched (and aren't cached) fails the request with the
  standard 503 body rather than returning a shorter season.
- Headers: `short` (60 s); `no-store` when stale, on `?refresh=1`, or with a scoreboard missing.

## Errors

| Status | Body |
|---|---|
| 404 | `{"error": "not_found"}`, including a week outside `start_week..current_week` and an unknown or in-progress season |
| 503 | `{"error": "yahoo_unavailable", "message": "..."}`, when Yahoo failed and nothing is cached |
| 500 | `{"error": "internal", "message": "..."}` |
