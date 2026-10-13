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
| `yahoo_client.py` | yfpy auth, fetch with timeout and retry, TTL cache, stale-on-error, refresh throttle | config, yfpy |
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
| Final weeks (fetched after the week ended) | Never expires | 1 day |

Finished weeks never change, so they are cached for the life of the instance. A week is only
marked final if it had already ended when fetched, so a mid-week snapshot is never frozen.

If Yahoo fails, the API returns the last cached data marked `stale`. A manual refresh skips
the cache at most once every 30 s per entry.

## Yahoo authentication

The consumer key, consumer secret and refresh token come from Secret Manager as env vars.
yfpy renews the access token in memory. Nothing is written to disk.
