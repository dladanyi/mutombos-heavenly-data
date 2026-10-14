# Sub-project 1: Stability refactor + backend/frontend split

- **Date:** 2026-10-12
- **Status:** Implemented on `stability-refactor` (PR #1). Waiting for Yahoo API access approval and the cutover.
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
- Runs on the Vercel Hobby plan: $0/month (Hobby has hard usage caps and never bills).
- `docs/` describes the system as built.

### Out of scope

Week picker, trends, matchups, browser end-to-end tests, infrastructure-as-code, multiple
leagues.

## 2. Problems in the current code

| Problem | Where | Fix in this design |
|---|---|---|
| Crash when `last_week == 0`: `last_week_table_html` is never assigned | `app.py` index route | Frontend hides the last-week section when `current_week == start_week` |
| 3-4 live Yahoo calls per page load, no cache | `app.py` | TTL cache in `yahoo_client` |
| No error handling | everywhere | Stale-on-error cache, JSON 503, UI error state |
| Token config mismatch (`YAHOO_ACCESS_TOKEN_JSON` vs separate vars) and token writes to `.env` on an ephemeral filesystem | `YahooFantasySportsQuery(...)` | Token data built in memory from Vercel env vars; never written to disk |
| Positional parsing (`t[0][2]['name']`) | `generate_rankings` | Key-based parsing in `parsing.py` |
| ~80 lines of JS re-read generated HTML to color cells | `table_view_fancy.html` | Colors come from API `rank` fields |
| `COPY . .` can copy a local `.env` into the image | `Dockerfile` | Docker removed (Vercel builds from Git; `.env` is git-ignored) |
| pandas + numpy (~150 MB) for ~30 lines of ranking | `requirements.txt` | Plain Python |
| Dead code: `table_view.html`, `cut_port_re`, duplicate `datetime` import, `pytz` | various | Removed |

## 3. Constraints

- **Hosting:** Vercel (Hobby plan), with the GitHub repo connected. A push to `main` deploys to
  production, and every other branch or PR gets a preview deployment. Decided 2026-10-12;
  replaces the earlier Cloud Run design (see `decisions.md`).
- **Cost:** $0/month. Hobby is free with hard caps; no paid add-ons.
- **Filesystem:** ephemeral. Nothing is persisted to disk at runtime.

## 4. Architecture

One repo, one Vercel project, one URL. Vercel's CDN serves the built React app as static
files, and the Flask app runs as a single Python function (Fluid Compute) for `/api/*` and
`/healthz`. Same origin, so no CORS.

```
Browser ──► Vercel CDN ─┬─ /*          frontend/dist (static, cached at the edge)
                        └─ /api/*, /healthz ──► CDN cache (per Vercel-CDN-Cache-Control)
                                                  └─ miss ──► Flask function ──► in-memory cache ──► Yahoo
```

Two cache layers protect Yahoo: the **CDN cache** (regional, shared by all visitors, survives
function cold starts) and the function's **in-memory cache** (per instance; still useful because
Fluid Compute reuses warm instances, and it is what serves stale data when Yahoo fails).

### Repository layout

```
backend/
  app/
    __init__.py        create_app() factory
    config.py          env vars (validated at startup), category definitions
    errors.py          YahooUnavailable, YahooFormatError
    yahoo_http.py      OAuth token refresh + GET with timeout, retry, 401 handling
    cache.py           TTL / final cache, stale-on-error, refresh throttle
    yahoo_client.py    league/season/week/calendar fetches, current/settling/final rules
    parsing.py         Yahoo JSON -> TeamStats / LeagueInfo / GameWeek
    rankings.py        list[TeamStats] -> ranked rows
    api.py             Flask blueprint: /api/*, /healthz, static frontend
    logging_setup.py   JSON log lines for Vercel runtime logs
  tests/
    fixtures/          real Yahoo responses, captured once
  scripts/
    get_refresh_token.py   one-time Yahoo login, prints a refresh token
    capture_fixtures.py
  requirements.txt     flask, requests
  requirements-dev.txt pytest
frontend/
  public/              halo_ball.png (favicon), header-left.jpg and header-right.jpg
                       (extracted from the base64 images inline in today's template)
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
vercel.json            build command, output dir, Python function, rewrites
docs/
```

Removed: `app.py`, `templates/`, `static/`, `Dockerfile`, `docker-compose.yml`,
`sample_data_table.txt`,
`51lCd0RlVSL._AC_.jpg` (not referenced by the app; the header images are inline in the
template and get extracted to `frontend/public/`).

## 5. Backend

### 5.1 Configuration (`config.py`)

| Variable | Source on Vercel | Required |
|---|---|---|
| `YAHOO_CONSUMER_KEY` | Project env var, marked Sensitive | yes |
| `YAHOO_CONSUMER_SECRET` | Project env var, marked Sensitive | yes |
| `YAHOO_REFRESH_TOKEN` | Project env var, marked Sensitive | yes |
| `YAHOO_LEAGUE_ID` | Project env var | yes |

Env vars are set for both Production and Preview. A missing required variable raises
`ConfigError` when `wsgi.py` imports the app, so the whole function fails to start, `/healthz`
included. Vercel returns its own 500, and the runtime log shows a plain traceback naming the
missing variables (not a JSON line). The static page still loads and shows its error card.
Check the preview deployment before merging to `main`.

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

### 5.2 Yahoo access (`yahoo_http.py`, `cache.py`, `yahoo_client.py`)

**No yfpy.** Our own small client using `requests` (see `decisions.md`, 2026-10-12).

- **Token:** POST `https://api.login.yahoo.com/oauth2/get_token` with HTTP Basic auth
  (consumer key and secret) and the form fields `grant_type=refresh_token`,
  `refresh_token=…` and `redirect_uri=oob`. The access token is kept in memory and renewed
  when it is missing or within 60 s of `expires_in`. If Yahoo returns a new refresh token, it
  is used from then on (in memory only). Token refresh is protected by a lock.
- **Requests:** GET `https://fantasysports.yahooapis.com/fantasy/v2/{path}?format=json` with
  `Authorization: Bearer …` and a 10 s timeout. One retry on timeout, connection error or 5xx.
  A 401 renews the token and retries once. Status 999 (Yahoo rate limit) is not retried. Any
  other failure, including a failed token refresh or a response that isn't JSON, raises
  `YahooUnavailable`. Nothing ever prompts for input or writes to disk.
- League key: `nba.l.{YAHOO_LEAGUE_ID}`.
- Thread-safe in-memory cache keyed by request path. Each entry stores the parsed JSON and its
  `fetched_at` time (UTC).

| Data | Server TTL |
|---|---|
| League metadata, season stats, current-week stats | 5 min |
| **Settling** week: ended, but less than 3 full days ago | 1 h |
| **Final** week: ended at least 3 full days before it was fetched | Never expires |
| Game-week calendar (start/end date of every week) | Never expires |

- **When a week becomes final.** Week end dates come from Yahoo's game-week calendar
  (`game/nba/game_weeks`). A week is final
  when the fetch happens on a date (America/Los_Angeles) more than 3 days after the week's end
  date. Example: a week ending Sunday the 9th is final from Thursday the 13th at 00:00 PT.
  The 3-day wait allows for Yahoo's stat corrections.
- Finality is decided **at fetch time** and stored on the entry. An entry fetched while the
  week was current or settling keeps its shorter TTL. The first fetch after the 3 days replaces
  it with a final entry. This prevents a mid-week or pre-correction snapshot being frozen.
- If the game-week calendar can't be loaded, no week is treated as final (safe default), and
  the calendar is retried on the next request.
- Final entries are never evicted. That's about 25 per season, a few KB each. Only in-memory,
  so they last until the instance shuts down, after which they are refetched once.
- **Stale on error:** if a fetch fails and an expired entry exists, it is returned with
  `stale=True`. Non-final entries are kept until evicted (LRU cap of 64 entries).
- **Refresh:** for a final entry, `refresh=True` is ignored and Yahoo is not called. For other
  entries, it bypasses the TTL, but only if the entry is more than 30 s old. Otherwise the
  cached entry is returned with `refresh_throttled=True`.
- Past seasons are out of scope here. When they are added, the same rule applies: a finished
  season is final.
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

| Endpoint | Returns |
|---|---|
| `GET /api/league` | name, current_week, start_week, end_week, categories |
| `GET /api/rankings/season` | season-to-date rankings |
| `GET /api/rankings/week/<n>`, `/current` or `/previous` | one week's rankings (`/previous` is 404 in the first week) |
| `GET /healthz` | `ok` (no Yahoo call) |

Each response sets a browser TTL (`Cache-Control`) and a CDN TTL (`Vercel-CDN-Cache-Control`):

| Data | `Cache-Control` (browser) | `Vercel-CDN-Cache-Control` (CDN) |
|---|---|---|
| League, season, current week, and the `/current` and `/previous` aliases in any state | `public, max-age=60` | `max-age=60` |
| Settling week | `public, max-age=300` | `max-age=3600` |
| Final week | `public, max-age=86400` | `max-age=31536000` |
| `?refresh=1`, `/healthz`, errors (4xx/5xx), stale responses | `no-store` | `no-store` |

- Final weeks get a 1-day browser cache instead of "forever". A browser that cached JSON
  forever could keep an old response shape after a deploy changes the API. The CDN cache
  doesn't have this problem because it is scoped to each deployment.
- The `/current` and `/previous` aliases point to a different week after each rollover, so they
  always get the 60 s headers, even when the week behind them is final. Only `/week/<n>` URLs
  get the long CDN cache, and the server-side cache still keeps final weeks forever. This also
  limits the damage if the calendar is wrong (§10 risk 3).
- Stale responses (Yahoo down) are never cached by the CDN, so normal data comes back as
  soon as Yahoo recovers.
- `?refresh=1` passes `refresh=True` to the client. It's a separate CDN cache key and is sent
  with `no-store`, so it always reaches the function. A week outside `start_week..current_week` returns 404 JSON.

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

Vercel serves the static frontend. A rewrite sends unknown non-API paths to `index.html`.
For local development, Flask also serves `frontend/dist` (the matching file, otherwise
`index.html`), so `npm run build` plus Flask works without Vercel.

### 5.6 Logging

JSON lines to stdout (`severity`, `message`, plus context fields such as the URL, duration and
cache hit/miss/stale), so Vercel's runtime logs can be filtered by field.

## 6. Frontend

- React + Vite + TypeScript on Node 22 LTS. No UI kit, state library, router or chart
  library in this sub-project.
- **Layout (same as today):** a header with the two side images, the title, and "Last
  updated" (taken from `fetched_at` and shown in `America/Los_Angeles` time by the browser).
  Then the current-week section (title, Refresh button, legend), the full-season section, and
  the last-week section when `current_week > start_week`. Each table has columns for Team, Avg Rank,
  and each category's value and rank. FG% and FT% show the detail beside them. Ranks 1-3 get
  gold, silver and bronze backgrounds, and `place` 1-3 does the same for Avg Rank.
- **States:** a loading skeleton, an error card with "Try again" (for 503 and network
  errors), a stale notice "Showing data as of …" when `stale` is true, a spinner on Refresh,
  and "Just refreshed" when `refresh_throttled` is true.
- **Styles:** today's CSS variables, Google Fonts (Bebas Neue, DM Mono, DM Sans), the scroll
  hint and the mobile/portrait media queries, ported to `styles.css`.
- **Development:** `npm run dev` proxies `/api` to Flask on `localhost:8080`.

## 7. Deployment (Vercel)

- **Project:** one Vercel project linked to the GitHub repo. Production branch: `main`. Every
  other branch and PR gets a preview URL.
- **`vercel.json`:**
  - two Services: `frontend` (Vite, static output) and `backend` (Flask as a Python 3.13
    function on Fluid Compute, entrypoint `wsgi:app`, dependencies from
    `backend/requirements.txt`). `backend/tests/**` is not excluded from the bundle yet; it is
    small and never imported.
  - rewrites: `/api/(.*)` and `/healthz` → `backend`; everything else → `frontend`

  The wiring was settled with `vercel build` and a preview deployment (§10.5); see
  `docs/deployment.md`.
- **Env vars:** set in Project → Settings → Environment Variables for Production and Preview.
  The three Yahoo secrets are marked Sensitive.
- **Cost:** Hobby plan. Usage is capped and never billed. If a cap is ever hit, functions
  pause until the next cycle rather than charging.
- **Local development:** Flask on `:8080` (`flask --app app:create_app run --port 8080` in
  `backend/`) plus `npm run dev` with the Vite proxy. `vercel dev` is optional.
- **Cutover** (each step needs the user's approval at the time):
  1. Create the project, add the env vars, and check the preview deployment of the
     `stability-refactor` branch. (Done.)
  2. Delete the Cloud Build trigger, so the merge doesn't start a Cloud Build of a tree with no
     Dockerfile.
  3. Merge to `main`, which deploys to production.
  4. Delete the Cloud Run service.
- **Rollback:** promote the previous production deployment (`vercel rollback`, or "Promote" in
  the dashboard).

## 8. CI (`.github/workflows/ci.yml`)

On every push and PR: `pytest` for the backend; `tsc --noEmit`, `vitest run` and `vite build`
for the frontend. Vercel's own build check runs on each preview deployment. The GitHub
ruleset "Protect main" requires a PR and green `backend` and `frontend` checks before
merging to `main` (live since 2026-10-13).

## 9. Testing

- **Fixtures:** `backend/scripts/capture_fixtures.py` saves real responses (league metadata,
  season, a week) to `backend/tests/fixtures/`.
- **`test_parsing.py`:** fixtures parse into 1 TeamStats per team; parsing still works with
  reordered keys; a malformed response raises `YahooFormatError`.
- **`test_rankings.py`:** ties share a rank, TO ranks lower-is-better, null values rank worst,
  plus avg/place/sort-order checks and detail strings.
- **`test_yahoo_http.py`** (with a fake session): token refresh and renewal, 401 → renew and
  retry, one retry on timeout or 5xx, no retry on 999, failed refresh → `YahooUnavailable`.
- **`test_cache.py` / `test_yahoo_client.py`** (with a fake transport): TTL expiry, final entries never expiring or being evicted, current/settling/final
  classification around the 3-day boundary (including the Pacific-time date edge), a week
  fetched while current or settling not becoming final, no week final when the calendar fails,
  refresh ignored for final entries,
  stale on error, `YahooUnavailable` when nothing is cached, the 30 s refresh throttle, and
  one retry.
- **`test_api.py`** (with a fake client): response shapes, 503 JSON, 404 for an out-of-range
  week, week 1, `Cache-Control` headers, and the SPA fallback.
- **Frontend:** RankCell medal classes; RankingsTable shows the FG%/FT% detail; App loading,
  error, stale and week-1 states, with `fetch` mocked.

## 10. Risks to verify early

1. ~~yfpy renewing from a refresh token alone~~ and 2. ~~request timeouts in yfpy~~:
   **resolved 2026-10-12.** yfpy 17.0.0 / yahoo-oauth 2.1.1 fall back to an interactive
   `input()` prompt when no access token is supplied, have no request timeout, use up their
   retries permanently per instance, and call `sys.exit(1)` on config errors. We replaced
   yfpy with our own client (5.2). The first backend task that talks to Yahoo verifies the
   refresh-token flow against the live API.
3. **Game-week calendar shape.** Confirm that `game_weeks` returns a start and end date for
   each week of this league's season (and capture it as a fixture). If the league's weeks
   differ from the game's calendar, use the league scoreboard's `week_start`/`week_end`
   instead. **Still open:** the fixtures are synthetic. After Yahoo approval, check that the
   `game_weeks` dates match this league's week numbering (including around the All-Star
   break) before trusting finality, since a week marked final too early gets a 1-year CDN
   cache.
4. **Fixture privacy: revisited 2026-10-13**, when the repo was made public.
   `capture_fixtures.py` strips every `managers` block (nickname, GUID, possibly an email)
   before writing. Team names stay: the production page already shows them publicly.
5. **Vercel Python wiring.** Confirm with `vercel build` (and a preview deployment) how the
   Flask app at `backend/app` becomes the function: the Services config or an `api/index.py`
   shim. Also confirm the `/api/*` rewrites, that `Vercel-CDN-Cache-Control` is honoured, and
   that responses carry `x-vercel-cache` `HIT` on repeat requests.
