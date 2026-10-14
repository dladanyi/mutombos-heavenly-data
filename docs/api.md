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
| `GET /healthz` | Returns `ok`; never calls Yahoo. If a required env var is missing the function can't start, so this returns Vercel's own 500 |

## Caching headers

| Data | `Cache-Control` | `Vercel-CDN-Cache-Control` |
|---|---|---|
| League, season, current week, and `/week/current` and `/week/previous` in any state | `public, max-age=60` | `max-age=60` |
| Week that ended less than 3 days ago | `public, max-age=300` | `max-age=3600` |
| Final week (ended 3+ days ago), by number only | `public, max-age=86400` | `max-age=31536000` |
| `?refresh=1`, `/healthz`, errors, stale responses | `no-store` | `no-store` |

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
      "place": 1,
      "stats": {"FG%": {"value": 0.482, "rank": 3, "detail": "301/624"}}
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

## Errors

| Status | Body |
|---|---|
| 404 | `{"error": "not_found"}`, including a week outside `start_week..current_week` |
| 503 | `{"error": "yahoo_unavailable", "message": "..."}`, when Yahoo failed and nothing is cached |
| 500 | `{"error": "internal", "message": "..."}` |
