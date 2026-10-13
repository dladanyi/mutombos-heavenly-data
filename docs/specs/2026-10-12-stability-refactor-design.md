# Sub-project 1: Stability refactor + backend/frontend split

- **Date:** 2026-10-12
- **Status:** Approved design, awaiting implementation plan
- **Branch:** `stability-refactor`

## 1. Goal

Make Mutombo's Heavenly Data stable, maintainable and free to run, and split it into a
JSON backend and a React frontend that later features can build on. The page users see
stays the same as today's dashboard.

This is the first of three sub-projects:

1. **Stability refactor + split** (this spec)
2. Pick any week + trends over time
3. Head-to-head matchups

### Success criteria

- The dashboard shows the same information and look as today: current week, full season, and
  last week, with medal colors, FG/FT made/attempted, and the mobile layout.
- Week 1 (no previous week) renders without error.
- A Yahoo failure never produces a raw 500 page. Users see cached data marked stale, or a
  friendly error with a retry button.
- Backend and frontend tests run in GitHub Actions on every push and PR.
- Runs within Google Cloud free tiers: $0/month at league-scale traffic.
- The final container image is under 300 MB.
- `docs/` describes the system as built.

### Out of scope

Week picker, trends, matchups, browser end-to-end tests, infrastructure-as-code, multiple
leagues.

## 2. Problems in the current code

| Problem | Where | Fix in this design |
|---|---|---|
| Crash when `last_week == 0`: `last_week_table_html` is never assigned | `app.py` index route | Frontend hides the last-week section when `current_week == 1` |
| 3-4 live Yahoo calls per page load, no cache | `app.py` | TTL cache in `yahoo_client` |
| No error handling | everywhere | Stale-on-error cache, JSON 503, UI error state |
| Token config mismatch (`YAHOO_ACCESS_TOKEN_JSON` vs separate vars) and token writes to `.env` on an ephemeral filesystem | `YahooFantasySportsQuery(...)` | Token data built in memory from env/Secret Manager; never written to disk |
| Positional parsing (`t[0][2]['name']`) | `generate_rankings` | Key-based parsing in `parsing.py` |
| ~80 lines of JS re-read generated HTML to color cells | `table_view_fancy.html` | Colors come from API `rank` fields |
| `COPY . .` without `.dockerignore` can copy a local `.env` into the image | `Dockerfile` | Add `.dockerignore` |
| `docker-compose.yml` mounts to `/code`, app lives in `/app` | `docker-compose.yml` | Fix the mount |
| pandas + numpy (~150 MB) for ~30 lines of ranking | `requirements.txt` | Plain Python |
| Dead code: `table_view.html`, `cut_port_re`, duplicate `datetime` import, `pytz` | various | Removed |

## 3. Constraints

- **Hosting:** Google Cloud Run, deployed by the existing Cloud Run GitHub link (Cloud Build
  trigger on push to `main`). The `Dockerfile` stays at the repo root.
- **Cost:** ideally $0/month. Scale to zero, no always-on instances, no paid add-ons.
- **Filesystem:** ephemeral. Nothing is persisted to disk at runtime.

## 4. Architecture

One repo, one container, one Cloud Run service, one URL. Flask serves both the JSON API and
the built React app (same origin, no CORS).

```
Browser ──► Cloud Run (gunicorn, 1 worker x 8 threads)
              ├─ /api/*      Flask JSON API ──► yahoo_client (TTL cache) ──► Yahoo Fantasy API
              ├─ /healthz    "ok"
              └─ /*          frontend/dist (React app)
```

### Repository layout

```
backend/
  app/
    __init__.py        create_app() factory
    config.py          env vars (validated at startup), category definitions
    yahoo_client.py    yfpy auth, fetch with timeout + 1 retry, TTL cache, refresh throttle
    parsing.py         Yahoo JSON -> list[TeamStats]
    rankings.py        list[TeamStats] -> Rankings
    api.py             Flask blueprint: /api/*, /healthz, static frontend
  tests/
    fixtures/          real Yahoo responses, captured once
  scripts/
    capture_fixtures.py
  requirements.txt     flask, gunicorn, yfpy
  requirements-dev.txt pytest
frontend/
  public/              halo_ball.png (favicon), header.jpg (renamed 51lCd0RlVSL._AC_.jpg)
  src/
    api.ts             typed fetch functions + types matching docs/api.md
    hooks/useApi.ts    loading / error / data / refetch
    components/Header.tsx
    components/RankingsSection.tsx
    components/RankingsTable.tsx
    components/RankCell.tsx
    styles.css         ported from table_view_fancy.html
    App.tsx, main.tsx
  package.json, vite.config.ts, tsconfig.json
.github/workflows/ci.yml
Dockerfile, .dockerignore, docker-compose.yml
docs/
```

Removed: `app.py`, `templates/`, `static/`, root `requirements.txt`, `sample_data_table.txt`,
`51lCd0RlVSL._AC_.jpg` (moved).

## 5. Backend

### 5.1 Configuration (`config.py`)

| Variable | Source on Cloud Run | Required |
|---|---|---|
| `YAHOO_CONSUMER_KEY` | Secret Manager | yes |
| `YAHOO_CONSUMER_SECRET` | Secret Manager | yes |
| `YAHOO_REFRESH_TOKEN` | Secret Manager | yes |
| `YAHOO_LEAGUE_ID` | plain env var | yes |
| `PORT` | set by Cloud Run | default `8080` |

A missing required variable makes startup fail with a clear log line. On Cloud Run, the new
revision then fails to start and traffic stays on the previous revision.

Categories are defined once, in display order:

| Key | Yahoo stat ID | Higher is better | Detail stat ID |
|---|---|---|---|
| PTS | 12 | yes | |
| REB | 15 | yes | |
| AST | 16 | yes | |
| ST | 17 | yes | |
| BLK | 18 | yes | |
| 3PTM | 10 | yes | |
| FG% | 5 | yes | 9004003 (FGM/FGA) |
| FT% | 8 | yes | 9007006 (FTM/FTA) |
| TO | 19 | no | |

### 5.2 Yahoo client (`yahoo_client.py`)

- Builds yfpy's token JSON in memory from the consumer key, secret and refresh token, with
  `save_token_data_to_env_file=False`. yfpy obtains and renews the access token itself.
- League key: `nba.l.{YAHOO_LEAGUE_ID}`.
- Every Yahoo request has a 10 s timeout and one retry on timeout, connection error or 5xx.
- Thread-safe in-memory cache keyed by request URL. Each entry stores the parsed JSON and its
  `fetched_at` time (UTC).

| Data | Server TTL |
|---|---|
| League metadata, season stats, current-week stats | 5 min |
| Any week before the current week | 6 h |

- **Stale on error:** if a fetch fails and an expired entry exists, it is returned with
  `stale=True`. Entries are kept until evicted (LRU cap of 64 entries).
- **Refresh:** `refresh=True` bypasses the TTL, but only if the entry is more than 30 s old.
  Otherwise the cached entry is returned with `refresh_throttled=True`.
- If a fetch fails and nothing is cached, it raises `YahooUnavailable`.

### 5.3 Parsing (`parsing.py`)

Turns a Yahoo `teams/stats` response into `list[TeamStats]`, where
`TeamStats = {team_key, name, values: {stat_id: raw_string}}`. Fields are found by key name,
so the order of Yahoo's list-of-dicts structures doesn't matter. Unknown stat IDs are
ignored. A response with an unexpected shape raises `YahooFormatError`, which the API treats
like `YahooUnavailable`.

### 5.4 Rankings (`rankings.py`)

- Value conversion: a numeric string becomes a float, or an int when it has no decimal point.
  `""`, `"-"` and `None` become `null`.
- Each category is ranked over teams with a non-null value, using the "min" tie method (tied
  teams share the best rank and the next rank is skipped). Higher values rank first unless the
  category is lower-is-better (TO). Teams with a null value get the worst rank (team count).
  *Change from today:* a missing TO currently becomes 0 and ranks best.
- `avg_rank` is the mean of the category ranks, rounded to 2 decimals.
- Teams are sorted by `avg_rank` ascending, then by name.
- `place` is the team's position by `avg_rank`, using the same min tie method. It drives
  the medal color on the average-rank column.

### 5.5 API (`api.py`)

| Endpoint | Returns | Browser `Cache-Control` |
|---|---|---|
| `GET /api/league` | name, current_week, start_week, end_week, categories | `max-age=60` |
| `GET /api/rankings/season` | season-to-date rankings | `max-age=60` |
| `GET /api/rankings/week/<n>` or `/current` | one week's rankings | `max-age=60` for the current week, `max-age=3600` for earlier weeks |
| `GET /healthz` | `ok` (no Yahoo call) | `no-store` |

`?refresh=1` on any `/api` endpoint passes `refresh=True` to the client and sends
`Cache-Control: no-store`. A week outside `start_week..current_week` returns 404 JSON.

Rankings response:

```json
{
  "scope": "week",
  "week": 7,
  "fetched_at": "2026-10-13T05:41:00Z",
  "stale": false,
  "refresh_throttled": false,
  "categories": [
    {"key": "PTS", "higher_is_better": true},
    {"key": "FG%", "higher_is_better": true, "detail_label": "FGM/FGA"},
    {"key": "TO", "higher_is_better": false}
  ],
  "teams": [
    {
      "name": "Team A",
      "avg_rank": 2.89,
      "place": 1,
      "stats": {
        "PTS": {"value": 812, "rank": 1},
        "FG%": {"value": 0.482, "rank": 3, "detail": "301/624"}
      }
    }
  ]
}
```

(`categories` and `stats` contain all nine categories. They are shortened here.) For
`/api/rankings/season`, `scope` is `"season"` and `week` is `null`.

Errors are always JSON: `{"error": "yahoo_unavailable", "message": "..."}` with status 503,
or `{"error": "not_found"}` with 404. Unhandled exceptions are logged with a stack trace and
return a 500 JSON body, never an HTML page.

Any other path serves `frontend/dist/index.html` or the matching static file.

### 5.6 Logging

JSON lines to stdout (`severity`, `message`, plus context fields such as the URL, duration and
cache hit/miss/stale), so Cloud Logging can parse them.

## 6. Frontend

- React + Vite + TypeScript on Node 22 LTS. No UI kit, state library, router or chart
  library in this sub-project.
- **Layout (same as today):** a header with the two side images, the title, and "Last
  updated" (taken from `fetched_at` and shown in `America/Los_Angeles` time by the browser).
  Then the current-week section (title, Refresh button, legend), the full-season section, and
  the last-week section when `current_week > 1`. Each table has columns for Team, Avg Rank,
  and each category's value and rank. FG% and FT% show the detail beside them. Ranks 1-3 get
  gold, silver and bronze backgrounds, and `place` 1-3 does the same for Avg Rank.
- **States:** a loading skeleton, an error card with "Try again" (for 503 and network
  errors), a stale notice "Showing data as of …" when `stale` is true, a spinner on Refresh,
  and "Just refreshed" when `refresh_throttled` is true.
- **Styles:** today's CSS variables, Google Fonts (Bebas Neue, DM Mono, DM Sans), the scroll
  hint and the mobile/portrait media queries, ported to `styles.css`.
- **Development:** `npm run dev` proxies `/api` to Flask on `localhost:8080`.

## 7. Deployment

- **Dockerfile** (repo root, multi-stage): stage 1 is `node:22-slim` and builds
  `frontend/dist`. Stage 2 is `python:3.12-slim` with the backend and the built frontend. The
  command is `gunicorn --workers 1 --threads 8 --bind :$PORT --chdir backend "app:create_app()"`.
- **`.dockerignore`:** `.env`, `.venv`, `node_modules`, `.git`, `.idea`, `docs`.
- **`docker-compose.yml`:** builds the same image and uses `.env` for local runs.
- **Cloud Run service settings:** `min-instances=0`, `max-instances=2`, 512 MiB of memory,
  1 vCPU, request-based billing, concurrency 80. Three secrets mounted as env vars from
  Secret Manager, plus `YAHOO_LEAGUE_ID`. Concurrency (80) is deliberately higher than
  gunicorn's thread count (8). Most requests are fast cache hits, so it's better for extra
  requests to wait briefly in gunicorn's queue than for Cloud Run to start a second instance
  with an empty cache.
- **Artifact Registry:** cleanup policy that keeps the 3 most recent images.
- **Billing:** a $1 budget alert as a guardrail.
- **Build/deploy:** unchanged. The Cloud Run GitHub link runs Cloud Build on push to `main`.
  Before the first deploy, check (read-only) that the trigger's build settings still point at
  the root `Dockerfile`.
- **Cutover:** move the secrets into Secret Manager and update the service settings, then
  merge to `main`. Check `/healthz` and `/api/league` on the new revision. To roll back,
  `gcloud run services update-traffic <service> --to-revisions <previous>=100`.

## 8. CI (`.github/workflows/ci.yml`)

On every push and PR: `pytest` for the backend; `tsc --noEmit` and `vitest run` for the
frontend; then `docker build`. We recommend turning on branch protection on `main` so that CI
must pass first.

## 9. Testing

- **Fixtures:** `backend/scripts/capture_fixtures.py` saves real responses (league metadata,
  season, a week) to `backend/tests/fixtures/`.
- **`test_parsing.py`:** fixtures parse into 1 TeamStats per team; parsing still works with
  reordered keys; a malformed response raises `YahooFormatError`.
- **`test_rankings.py`:** ties share a rank, TO ranks lower-is-better, null values rank worst,
  plus avg/place/sort-order checks and detail strings.
- **`test_yahoo_client.py`** (with a fake transport): TTL expiry, the 5 min / 6 h split,
  stale on error, `YahooUnavailable` when nothing is cached, the 30 s refresh throttle, and
  one retry.
- **`test_api.py`** (with a fake client): response shapes, 503 JSON, 404 for an out-of-range
  week, week 1, `Cache-Control` headers, and the SPA fallback.
- **Frontend:** RankCell medal classes; RankingsTable shows the FG%/FT% detail; App loading,
  error, stale and week-1 states, with `fetch` mocked.

## 10. Risks to verify early

1. **yfpy renewing from a refresh token alone.** The first implementation task proves that
   `YahooFantasySportsQuery` renews the access token from consumer key, secret and refresh
   token with no interactive prompt and no file writes. If it can't, the client performs the
   OAuth refresh itself (a single POST to Yahoo's token endpoint) and passes the result to
   yfpy.
2. **Request timeouts in yfpy.** If `get_response` doesn't accept a timeout, the client calls
   the OAuth session that yfpy has already authenticated directly, with `timeout=10`.
3. **Fixture privacy.** Fixtures contain real team names. Check whether the GitHub repo is
   public before committing them. If it is, replace the names with placeholders.
