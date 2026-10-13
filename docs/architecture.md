# Architecture

> **Status:** describes the target design from sub-project 1
> ([spec](specs/2026-10-12-stability-refactor-design.md)). Not yet implemented.

## Overview

One repo, one container, one Cloud Run service. Flask serves the JSON API and the built React
app from the same origin.

```
Browser ──► Cloud Run (gunicorn, 1 worker x 8 threads, scales to zero)
              ├─ /api/*      Flask JSON API ──► yahoo_client (in-memory TTL cache) ──► Yahoo Fantasy API
              ├─ /healthz    liveness check, no Yahoo call
              └─ /*          React app (frontend/dist)
```

## Backend (`backend/app/`)

| Module | Responsibility | Depends on |
|---|---|---|
| `config.py` | Reads and validates env vars; defines the nine ranked categories | - |
| `errors.py` | `YahooUnavailable`, `YahooFormatError` | - |
| `yahoo_http.py` | OAuth token refresh, GET with timeout, retry and 401 handling | requests |
| `cache.py` | TTL / final cache, stale-on-error, refresh throttle | - |
| `yahoo_client.py` | League, season, week and calendar fetches; current/settling/final rules | yahoo_http, cache, parsing |
| `logging_setup.py` | JSON log lines for Cloud Logging | - |
| `parsing.py` | Yahoo `teams/stats` JSON → `TeamStats` | config |
| `rankings.py` | `TeamStats` → ranked table (per-category ranks, avg rank, place) | config |
| `api.py` | Flask routes, JSON errors, cache headers, serves the frontend | all of the above |

`parsing` and `rankings` are pure functions, tested against saved Yahoo responses.

## Frontend (`frontend/src/`)

React + Vite + TypeScript. `api.ts` holds typed fetch functions whose types mirror
[api.md](api.md). Components: `Header`, `RankingsSection`, `RankingsTable`, `RankCell`.
Medal colors come from the API's `rank` and `place` fields.

## Caching

The cache is in memory, one per Cloud Run instance, and is lost when the service scales to
zero. That is intentional: it keeps the app free and refills on the next request.

| Data | Server TTL | Browser max-age |
|---|---|---|
| League, season, current week | 5 min | 60 s |
| Settling weeks (ended less than 3 days ago) | 1 h | 5 min |
| Final weeks (ended 3+ days before fetch) | Never expires | 1 day |

A week becomes final once it is more than 3 days past its end date (Pacific time, using
Yahoo's game-week calendar), which leaves time for Yahoo's stat corrections. Finality is
decided when the data is fetched, so a mid-week or pre-correction snapshot is never frozen.
Final weeks are cached for the life of the instance.

If Yahoo fails, the API returns the last cached data marked `stale`. A manual refresh skips
the cache at most once every 30 s per entry.

## Yahoo authentication

The consumer key, consumer secret and refresh token come from Secret Manager as env vars.
`yahoo_http.py` exchanges the refresh token for an access token in memory and renews it
before it expires (tokens last 1 h). It never prompts for input and never writes to disk.
