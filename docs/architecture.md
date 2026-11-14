# Architecture

> **Status:** implemented on branch `stability-refactor`; not yet deployed
> ([spec](specs/2026-10-12-stability-refactor-design.md)).

## Overview

One repo, one Vercel project, one URL. Vercel's CDN serves the React app as static files, and
the Flask app runs as a single Python function for `/api/*` and `/healthz`.

```
Browser ──► Vercel CDN ─┬─ /*          frontend/dist (static)
                        └─ /api/*, /healthz ──► CDN cache
                                                  └─ miss ──► Flask function ──► in-memory cache ──► Yahoo Fantasy API
```

## Backend (`backend/app/`)

| Module | Responsibility | Depends on |
|---|---|---|
| `config.py` | Reads and validates env vars; defines the nine ranked categories | - |
| `errors.py` | `YahooUnavailable`, `YahooFormatError`, `YahooAccessDenied` (HTTP 403) | - |
| `yahoo_http.py` | OAuth token refresh, GET with timeout, retry and 401 handling | requests |
| `cache.py` | TTL / final cache, stale-on-error, refresh throttle | - |
| `yahoo_client.py` | League, season, week, scoreboard and calendar fetches; current/settling/final rules; past-season walk (`renew`) and final standings; top-50 players (1 h) | yahoo_http, cache, parsing |
| `parsing.py` | Yahoo JSON → `TeamStats`, `LeagueInfo`, `GameWeek`, `MatchupResult`, `Standing`, `RankedPlayer` | config |
| `rankings.py` | `TeamStats` → ranked table (per-category ranks, avg rank, median rank, place) | config |
| `stars.py` | Ranked players + teams → Star Power (top-10/25/50 counts, order, unowned) | parsing |
| `api.py` | Flask routes, JSON errors, cache headers, local static serving | all of the above |
| `logging_setup.py` | JSON log lines (Vercel runtime logs) | - |

`backend/wsgi.py` is the Vercel entrypoint (`app = create_app()`).

`parsing` and `rankings` are pure functions, tested against saved Yahoo responses.

## Frontend (`frontend/src/`)

React + Vite + TypeScript. `api.ts` holds typed fetch functions whose types mirror
[api.md](api.md). A tab bar (`TabBar`) switches between two screens, kept in the URL hash
(`#stars` = Star Power) so a screen can be bookmarked and Back works. Star Power
(`StarPowerSection`, `StarPowerTable`) loads only when its tab is opened. The Rankings screen has
two sections: the week section (opens on the live week; ‹ ›
step back through finished weeks via `/api/rankings/week/<n>`) and Full Season. Components:
`Header`, `RankingsSection`, `RankingsTable`, `RankCell`, `ArrowNav` (the shared ‹ › buttons),
`FullSeasonSection` (the ‹ › season arrows; today's view while a season is in progress, the
final view once finished) and `StandingsTable` (champion line and final standings, with each team's Avg/Med Rk and
per-category ranks next to its finish).
Medal colors come from the API's `rank` and `place` fields. A finished season's medals are on
its standings, so its rankings table doesn't colour Avg Rank.

## Caching

Two layers:

- **Vercel CDN:** regional and shared by every visitor. It survives function cold starts and
  is scoped to the deployment.
- **In-memory cache in the function:** per instance. Fluid Compute reuses warm instances, so
  it catches repeat misses. It is also what serves the last good data when Yahoo fails.

| Data | In-memory TTL | CDN | Browser |
|---|---|---|---|
| League, season, current week | 5 min | 60 s | 60 s |
| Settling week (ended less than 3 days ago) | 1 h | 1 h | 5 min |
| Final week (ended 3+ days before fetch) | forever | 1 year | 1 day |
| Season list (`/api/seasons`) | current league 5 min, previous leagues 1 day | 60 s | 60 s |
| Finished season's standings and stats | forever | 1 year | 1 day |
| Star Power (top-50 players) | 1 h | 1 h | 5 min |

A week becomes final once it is more than 3 days past its end date (Pacific time, using
Yahoo's game-week calendar), which leaves time for Yahoo's stat corrections. Finality is
decided when the data is fetched, so a mid-week or pre-correction snapshot is never frozen.
Stale responses (served from memory when Yahoo fails) and `?refresh=1` responses are never
cached by the CDN or the browser. A manual refresh skips the in-memory cache at most once
every 30 s per entry. After a Yahoo failure, that entry isn't retried for 30 s (stale data or a
fast 503 instead), and a failed token refresh isn't retried for 30 s either, so an outage or
rate limit doesn't turn into one slow Yahoo call per visitor.

## Yahoo authentication

The consumer key, consumer secret and refresh token come from Vercel environment variables.
`yahoo_http.py` exchanges the refresh token for an access token in memory and renews it
before it expires (tokens last 1 h). It never prompts for input and never writes to disk.
