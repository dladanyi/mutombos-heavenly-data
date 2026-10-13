# Stability Refactor + Backend/Frontend Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-file Flask app with a tested Flask JSON API and a React frontend
deployed on Vercel (Hobby, $0/month) that looks the same as today's dashboard.

**Architecture:** `backend/app/` holds small single-purpose modules: config, our own Yahoo
HTTP client, a cache with current/settling/final rules, parsing, rankings, and Flask routes.
`frontend/` is a Vite + React + TypeScript app built into `frontend/dist`. Vercel serves
the static frontend from its CDN and runs Flask as one Python function for `/api/*` and
`/healthz`, deploying from GitHub. (Hosting moved from Cloud Run to Vercel on 2026-10-12;
see `docs/decisions.md`.)

**Tech Stack:** Python 3.12, Flask, requests, pytest; Node 22, React, Vite, TypeScript,
Vitest, Testing Library; Vercel; GitHub Actions.

**Spec:** `docs/specs/2026-10-12-stability-refactor-design.md`. Read it before starting any
task; section numbers below (§) refer to it.

## Global Constraints

- Work on branch `stability-refactor`. Never push to `main` (a push to `main` deploys to production: Cloud Run today, Vercel after cutover).
- Backend runtime dependencies are exactly `flask` and `requests` (Task 1 added `gunicorn`; Task 10 removes it). No yfpy, pandas, pytz or jmespath.
- Python 3.12 on Vercel and in CI. Code must also run on the local `.venv` (Python 3.13).
- Never write tokens or secrets to disk or logs. Never print a token value; scripts print only what the user needs to copy.
- Nothing may call `input()` or block waiting for a person at runtime.
- Yahoo requests use a 10 s timeout.
- Cache timings: current/league/season 300 s; settling week 3600 s; final week and game-week calendar never expire; refresh throttle 30 s; non-final LRU cap 64.
- A week is final when `today_pacific > week_end + 3 days` at fetch time. Pacific means `America/Los_Angeles` via `zoneinfo`.
- Headers (`Cache-Control` / `Vercel-CDN-Cache-Control`): league, season, current week `public, max-age=60` / `max-age=60`; settling `public, max-age=300` / `max-age=3600`; final `public, max-age=86400` / `max-age=31536000`; `?refresh=1`, `/healthz`, errors and stale responses `no-store` / `no-store`.
- Categories in display order: PTS(12), REB(15), AST(16), ST(17), BLK(18), 3PTM(10), FG%(5, detail 9004003 "FGM/FGA"), FT%(8, detail 9007006 "FTM/FTA"), TO(19, lower is better).
- Hosting: Vercel Hobby, Python 3.12 function, env vars `YAHOO_CONSUMER_KEY`, `YAHOO_CONSUMER_SECRET`, `YAHOO_REFRESH_TOKEN` (Sensitive) and `YAHOO_LEAGUE_ID` (now `46425`).
- Docs: every task that changes architecture, API or deployment updates the matching file in `docs/` in the same commit (see `docs/README.md`).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Preseason or start of a week: every stat value is `""` or `"-"`.** The page should render with every team tied, values shown as "–", and no crash. Tests: Task 5 `test_all_values_missing_ties_everyone`; Task 9 `RankCell renders dash for null`.
2. **A team name containing `<`, `&`, an apostrophe or an emoji.** It should display literally, never as HTML. Test: Task 9 `renders team names as text`.
3. **Yahoo rate limit (HTTP 999).** No retry storm: one call, then stale data or 503. Tests: Task 2 `test_999_not_retried`; Task 4 `test_failure_serves_stale`.
4. **Refresh token revoked or invalid (token endpoint returns 400).** Requests fail fast with `YahooUnavailable` (logged, never printing the token), and users see stale data or the error card, never a hang. Test: Task 2 `test_token_refresh_failure_raises_unavailable`.
5. **Several visitors open the page at once on a cold instance.** One Yahoo call per resource, not one per visitor. Test: Task 4 `test_concurrent_misses_fetch_once`.

---

## File Map

| File | Responsibility |
|---|---|
| `backend/app/__init__.py` | `create_app()` |
| `backend/app/config.py` | `Settings`, `load_settings`, `Category`, `CATEGORIES`, `ConfigError` |
| `backend/app/errors.py` | `YahooUnavailable`, `YahooFormatError` |
| `backend/app/yahoo_http.py` | `YahooHttp`: token refresh + `get_json` |
| `backend/app/parsing.py` | `TeamStats`, `LeagueInfo`, `GameWeek`, parse functions |
| `backend/app/rankings.py` | `to_number`, `build_rankings` |
| `backend/app/cache.py` | `Cache`, `CacheResult` |
| `backend/app/yahoo_client.py` | `YahooClient`, `WeekState`, `pacific_today` |
| `backend/app/api.py` | Flask blueprint, error handlers, static/SPA serving |
| `backend/app/logging_setup.py` | `configure_logging()` (JSON lines) |
| `backend/scripts/get_refresh_token.py` | One-time Yahoo login |
| `backend/scripts/capture_fixtures.py` | Saves live Yahoo responses as fixtures |
| `backend/tests/…` | pytest suites and `fixtures/*.json` |
| `frontend/src/api.ts` | Types + fetch functions |
| `frontend/src/hooks/useApi.ts` | Data-loading hook |
| `frontend/src/components/*.tsx` | `Header`, `RankingsSection`, `RankingsTable`, `RankCell` |
| `frontend/src/App.tsx`, `main.tsx`, `styles.css` | Page composition and styles |
| `vercel.json` (+ `api/index.py` shim if needed) | Vercel build, function and rewrites |
| `.github/workflows/ci.yml` | CI |

Removed in Tasks 10-11: `app.py`, `templates/`, `static/`, root `requirements.txt`,
`Dockerfile`, `docker-compose.yml`, `sample_data_table.txt`, `51lCd0RlVSL._AC_.jpg`.

---

### Task 1: Backend skeleton, config and errors

**Files:**
- Create: `backend/app/__init__.py` (empty for now), `backend/app/config.py`, `backend/app/errors.py`, `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pytest.ini`, `backend/tests/__init__.py`, `backend/tests/test_config.py`
- Modify: `.gitignore` (add `node_modules/`, `frontend/dist/`, `__pycache__/`, `.pytest_cache/`)

**Interfaces:**
- Produces:
  - `config.Category(key: str, stat_id: str, higher_is_better: bool, detail_stat_id: str | None = None, detail_label: str | None = None)`, a frozen dataclass
  - `config.CATEGORIES: tuple[Category, ...]` in the Global Constraints order
  - `config.Settings(consumer_key: str, consumer_secret: str, refresh_token: str, league_id: str, port: int)`, a frozen dataclass
  - `config.load_settings(env: Mapping[str, str] = os.environ) -> Settings`
  - `config.ConfigError(Exception)`
  - `errors.YahooUnavailable(Exception)`; `errors.YahooFormatError(YahooUnavailable)`

- [ ] **Step 1: Set up the environment.** `requirements.txt`: `flask~=3.1`, `gunicorn~=25.0`, `requests~=2.32`. `requirements-dev.txt`: `-r requirements.txt`, `pytest~=8.3`. `pytest.ini`: `[pytest]` with `testpaths = tests` and `pythonpath = .`. Run `.venv/bin/pip install -r backend/requirements-dev.txt`.
- [ ] **Step 2: Write failing tests in `test_config.py`:**

```python
def test_load_settings_reads_required_vars():
    s = load_settings({"YAHOO_CONSUMER_KEY": "k", "YAHOO_CONSUMER_SECRET": "s",
                       "YAHOO_REFRESH_TOKEN": "r", "YAHOO_LEAGUE_ID": "123"})
    assert (s.consumer_key, s.league_id, s.port) == ("k", "123", 8080)

def test_port_from_env():
    assert load_settings({**REQUIRED, "PORT": "9000"}).port == 9000

@pytest.mark.parametrize("missing", ["YAHOO_CONSUMER_KEY", "YAHOO_CONSUMER_SECRET",
                                     "YAHOO_REFRESH_TOKEN", "YAHOO_LEAGUE_ID"])
def test_missing_var_raises_config_error_naming_it(missing):
    env = {k: v for k, v in REQUIRED.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        load_settings(env)

def test_empty_string_counts_as_missing():
    with pytest.raises(ConfigError):
        load_settings({**REQUIRED, "YAHOO_LEAGUE_ID": ""})

def test_categories_order_and_flags():
    assert [c.key for c in CATEGORIES] == ["PTS","REB","AST","ST","BLK","3PTM","FG%","FT%","TO"]
    assert [c.key for c in CATEGORIES if not c.higher_is_better] == ["TO"]
    fg = next(c for c in CATEGORIES if c.key == "FG%")
    assert (fg.stat_id, fg.detail_stat_id, fg.detail_label) == ("5", "9004003", "FGM/FGA")

def test_yahoo_format_error_is_unavailable():
    assert issubclass(YahooFormatError, YahooUnavailable)
```

- [ ] **Step 3: Run** `cd backend && ../.venv/bin/pytest tests/test_config.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 4: Implement `config.py` and `errors.py`** with the interfaces above. The `ConfigError` message lists every missing variable name and never includes values.
- [ ] **Step 5: Run the tests again.** Expected: all PASS.
- [ ] **Step 6: Commit** `feat(backend): add config, categories and error types`.

---

### Task 2: Yahoo HTTP client

**Files:**
- Create: `backend/app/yahoo_http.py`, `backend/tests/test_yahoo_http.py`

**Interfaces:**
- Consumes: `errors.YahooUnavailable`
- Produces:
  - `TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"`
  - `API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2/"`
  - `class YahooHttp(consumer_key: str, consumer_secret: str, refresh_token: str, *, session: requests.Session | None = None, clock: Callable[[], float] = time.time, timeout: float = 10.0)`
  - `YahooHttp.get_json(path: str) -> dict`, where `path` is relative to `API_BASE` (e.g. `"league/nba.l.123"`)

Behavior (§5.2): the token POST uses Basic auth with `data={"grant_type": "refresh_token", "refresh_token": …, "redirect_uri": "oob"}` and the timeout. The token is renewed when missing or when `clock() >= obtained_at + expires_in - 60`. A `refresh_token` in the token response replaces the stored one. GET sends `params={"format": "json"}`, the `Authorization: Bearer <token>` header and the timeout. Retry once on `requests.Timeout`, `requests.ConnectionError` or status ≥ 500. On 401, renew and retry once. On 999, no retry. Anything else non-2xx, invalid JSON, or a failed or non-2xx token call raises `YahooUnavailable` with a message containing the status and path, never a token. Use a `threading.Lock` around renewal. Log each failed attempt at `warning` with `path`, `status` and `attempt`.

- [ ] **Step 1: Write failing tests** with a `FakeSession` whose `post`/`get` return queued `FakeResponse(status, json_body | None)` objects or raise queued exceptions, and record their calls:

```python
def test_first_call_fetches_token_then_data():  # 1 post, 1 get; Authorization == "Bearer t1"; params == {"format": "json"}; timeout == 10.0
def test_token_reused_until_60s_before_expiry():  # expires_in=3600; clock 3539 → no new post; clock 3541 → new post
def test_new_refresh_token_is_used_next_time():   # 2nd token post's data["refresh_token"] == value returned by 1st
def test_401_renews_token_and_retries_once():      # get statuses [401, 200] → 2 posts, 2 gets, returns body
def test_retry_once_on_timeout():                  # get raises Timeout then 200 → returns body; 2 gets
def test_retry_once_on_500_then_raise():           # [500, 503] → YahooUnavailable; exactly 2 gets
def test_999_not_retried():                        # [999] → YahooUnavailable; exactly 1 get
def test_404_raises_without_retry():               # [404] → YahooUnavailable; 1 get
def test_invalid_json_raises_unavailable():        # 200 with non-JSON body → YahooUnavailable
def test_token_refresh_failure_raises_unavailable():  # post → 400 → YahooUnavailable; no get; "r-secret" not in str(exc)
```

- [ ] **Step 2: Run** `../.venv/bin/pytest tests/test_yahoo_http.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement `YahooHttp`.**
- [ ] **Step 4: Run the tests again.** Expected: all PASS.
- [ ] **Step 5: Commit** `feat(backend): add Yahoo HTTP client with token refresh, timeout and retry`.

---

### Task 3: Live Yahoo check, refresh-token script and fixtures

This task talks to the real Yahoo API using the user's local `.env`. It is the live check for
the token flow, and it closes §10 risk 3. **The fixtures must exist before Tasks 5-7.**

**Files:**
- Create: `backend/scripts/get_refresh_token.py`, `backend/scripts/capture_fixtures.py`, `backend/tests/fixtures/{league,season_stats,week_stats,game_weeks}.json`
- Modify: `docs/deployment.md` (replace the "Getting a Yahoo refresh token" placeholder with the real steps)

**Interfaces:**
- Consumes: `YahooHttp`, `load_settings`
- Produces: four fixture files used by Tasks 4, 6 and 7:
  - `league.json` ← `league/nba.l.{id}`
  - `season_stats.json` ← `league/nba.l.{id}/teams/stats`
  - `week_stats.json` ← `league/nba.l.{id}/teams/stats;type=week;week={w}`, where `w` is the most recent completed week (or the current week in week 1)
  - `game_weeks.json` ← `game/nba/game_weeks`

- [ ] **Step 1: Write `get_refresh_token.py`.** It reads `YAHOO_CONSUMER_KEY`/`YAHOO_CONSUMER_SECRET` from the environment and prints the authorize URL `https://api.login.yahoo.com/oauth2/request_auth?client_id=…&redirect_uri=oob&response_type=code`. It reads the code the user pastes, POSTs `grant_type=authorization_code` to `TOKEN_URL`, and prints only the refresh token with the instruction "store this in Secret Manager as YAHOO_REFRESH_TOKEN". This is a local, manual script and the only place `input()` is allowed.
- [ ] **Step 2: Write `capture_fixtures.py`.** It loads settings from the environment, uses `YahooHttp`, and writes the four responses as pretty-printed JSON. It prints only the file names and sizes.
- [ ] **Step 3: Run it** from the repo root: `set -a; source .env; set +a; .venv/bin/python backend/scripts/capture_fixtures.py`. Expected: 4 files are written with no exception. That proves the refresh-token flow works without an access token. If the token call returns 400 `invalid_grant`, stop and ask the user to run `get_refresh_token.py` and update `.env`.
- [ ] **Step 4: Inspect the fixtures and record their shapes** in a short docstring at the top of `parsing.py`'s test file (Task 4). Confirm `game_weeks.json` has `start`/`end` dates for every week from the league's `start_week` to `end_week`. **If it doesn't, stop and tell the user**, because §10 risk 3 then needs the scoreboard fallback.
- [ ] **Step 5: Update `docs/deployment.md`** with how to run `get_refresh_token.py`.
- [ ] **Step 6: Commit** `chore(backend): add refresh-token and fixture capture scripts with live fixtures`.

---

### Task 4: Cache

**Files:**
- Create: `backend/app/cache.py`, `backend/tests/test_cache.py`

**Interfaces:**
- Consumes: `errors.YahooUnavailable`
- Produces:
  - `CacheResult(data: Any, fetched_at: float, stale: bool, refresh_throttled: bool, final: bool)`, a frozen dataclass
  - `class Cache(clock: Callable[[], float] = time.time, max_entries: int = 64, refresh_min_age: float = 30.0)`
  - `Cache.get_or_fetch(key: str, fetch: Callable[[], Any], ttl: float | None, refresh: bool = False) -> CacheResult`, where `ttl=None` stores the entry as final

Rules (§5.2), in order:
1. A final entry is always returned (`refresh` ignored, no fetch).
2. A fresh entry with no refresh is returned.
3. Refresh on an entry younger than `refresh_min_age` returns it with `refresh_throttled=True`.
4. Otherwise fetch. On success, store it with the `ttl` passed to *this* call. On `YahooUnavailable`, return the existing entry with `stale=True`, or re-raise if there is none.

Non-final entries are LRU-evicted beyond `max_entries`. Final entries are never evicted.
Use a per-key `threading.Lock` so concurrent misses on the same key call `fetch` once.

- [ ] **Step 1: Write failing tests** with a fake clock and a counting fetch:

```python
def test_miss_fetches_and_caches():            # 2 calls → fetch count 1
def test_ttl_expiry_refetches():               # ttl=300; clock+301 → fetch count 2
def test_final_entry_never_expires():          # ttl=None; clock+10 years → count 1; result.final is True
def test_refresh_ignored_for_final():          # refresh=True on final → count 1, refresh_throttled False
def test_refresh_bypasses_ttl_after_30s():     # clock+31, refresh=True → count 2
def test_refresh_throttled_within_30s():       # clock+10, refresh=True → count 1, refresh_throttled True
def test_failure_serves_stale():               # cached then expired; fetch raises YahooUnavailable → stale True, old data
def test_failure_without_entry_raises():       # → YahooUnavailable
def test_ttl_taken_from_the_call_that_fetched():  # first ttl=300, after expiry ttl=None → later never refetches
def test_lru_evicts_oldest_non_final_only():   # max_entries=2; 1 final + 3 non-final → final kept, oldest non-final evicted
def test_concurrent_misses_fetch_once():       # 8 threads, slow fetch (Event-gated) → count 1, all get same data
```

- [ ] **Step 2: Run** `../.venv/bin/pytest tests/test_cache.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `Cache`.**
- [ ] **Step 4: Run the tests again.** Expected: all PASS.
- [ ] **Step 5: Commit** `feat(backend): add cache with final entries, stale-on-error and refresh throttle`.

---

### Task 5: Parsing and rankings

**Files:**
- Create: `backend/app/parsing.py`, `backend/app/rankings.py`, `backend/tests/test_parsing.py`, `backend/tests/test_rankings.py`

**Interfaces:**
- Consumes: `CATEGORIES`, `Category`, `YahooFormatError`, Task 3 fixtures
- Produces:
  - `TeamStats(team_key: str, name: str, values: dict[str, str | None])`, keyed by Yahoo stat_id
  - `LeagueInfo(name: str, current_week: int, start_week: int, end_week: int)`
  - `GameWeek(week: int, start: datetime.date, end: datetime.date)`
  - `parse_team_stats(payload: dict) -> list[TeamStats]`
  - `parse_league(payload: dict) -> LeagueInfo`
  - `parse_game_weeks(payload: dict) -> dict[int, GameWeek]`
  - `rankings.to_number(raw: str | None) -> int | float | None`
  - `rankings.build_rankings(teams: list[TeamStats], categories: Sequence[Category] = CATEGORIES) -> list[dict]`, where each row is `{"name", "avg_rank", "place", "stats": {key: {"value", "rank", "detail"?}}}` exactly as in §5.5

Parsing finds fields by key name: merge the single-key dicts in a team's metadata list, and
locate the element containing `team_stats` wherever it sits. A missing required key or wrong
type raises `YahooFormatError` with the path. Ranking rules are in §5.4. `to_number`:
`"301/624"` is not a number (return `None`; it's only used as detail), `".482"` becomes 0.482,
`"812"` becomes 812, and `""`/`"-"`/`None` become `None`.

- [ ] **Step 1: Write failing parsing tests:**

```python
def test_season_fixture_parses_one_row_per_team():    # len == league team count; names non-empty; "5" in values
def test_week_fixture_has_fg_detail():                 # values["9004003"] matches r"^\d+/\d+$"
def test_team_metadata_order_does_not_matter():        # reverse each team's metadata list → same result
def test_missing_teams_raises_format_error():          # {"fantasy_content": {"league": [{}]}} → YahooFormatError
def test_parse_league_fixture():                       # current_week/start_week/end_week are ints; start <= current <= end
def test_parse_game_weeks_fixture():                   # keys cover start_week..end_week; each start <= end; dates are datetime.date
```

- [ ] **Step 2: Write failing ranking tests** with hand-built `TeamStats`:

```python
def test_to_number():   # ".482"→0.482, "812"→812, "-"→None, ""→None, None→None, "301/624"→None
def test_higher_is_better_rank():       # PTS 100,90,80 → ranks 1,2,3
def test_turnovers_lower_is_better():   # TO 10,20,30 → ranks 1,2,3
def test_ties_use_min_method():         # PTS 100,100,80 → 1,1,3
def test_null_ranks_worst():            # PTS 100,None,80 → 1,3,2; value None
def test_null_turnovers_rank_worst():   # TO 10,None → 1,2
def test_avg_rank_rounded_and_sorted(): # avg of 9 ranks rounded to 2 dp; rows sorted by avg_rank then name
def test_place_uses_min_ties():         # avg 1.5,1.5,3.0 → place 1,1,3
def test_detail_attached_to_fg_ft():    # stats["FG%"]["detail"] == "301/624"; no "detail" key on PTS
def test_all_values_missing_ties_everyone():  # every value "-" → every rank == team count, every place == 1, values None
def test_season_fixture_end_to_end():   # build_rankings(parse_team_stats(fixture)) → 9 stats per row, places start at 1
```

- [ ] **Step 3: Run** `../.venv/bin/pytest tests/test_parsing.py tests/test_rankings.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement `parsing.py` and `rankings.py`.**
- [ ] **Step 5: Run the tests again.** Expected: all PASS.
- [ ] **Step 6: Commit** `feat(backend): add key-based parsing and plain-Python rankings`.

---

### Task 6: Yahoo client (week states, caching policy)

**Files:**
- Create: `backend/app/yahoo_client.py`, `backend/tests/test_yahoo_client.py`

**Interfaces:**
- Consumes: `YahooHttp.get_json`, `Cache`, `CacheResult`, the parse functions, `GameWeek`, `LeagueInfo`, `TeamStats`
- Produces:
  - `WeekState = Literal["current", "settling", "final"]`
  - `pacific_today() -> datetime.date`, using `ZoneInfo("America/Los_Angeles")`
  - `CURRENT_TTL = 300`, `SETTLING_TTL = 3600`, `FINAL_DELAY_DAYS = 3`
  - `class YahooClient(http, league_id: str, cache: Cache, today: Callable[[], date] = pacific_today)`
  - `.league(refresh: bool = False) -> tuple[LeagueInfo, CacheResult]` (TTL 300)
  - `.season_stats(refresh: bool = False) -> tuple[list[TeamStats], CacheResult]` (TTL 300)
  - `.week_state(week: int, current_week: int) -> WeekState`
  - `.week_stats(week: int, current_week: int, refresh: bool = False) -> tuple[list[TeamStats], CacheResult, WeekState]`

`http` is any object with `get_json(path) -> dict`, so tests pass a fake. Paths are as in
Task 3. Parsing happens inside the `fetch` callable, so a `YahooFormatError` goes through the
cache's stale path. `week_state`: `week >= current_week` is `"current"`. Otherwise load the
calendar (cached with `ttl=None` under the key `"game_weeks"`). If that raises
`YahooUnavailable`, or the week is missing from it, return `"settling"`. Otherwise
`"final" if today() > end + timedelta(days=3) else "settling"`. `week_stats` computes the
state *before* fetching and passes `None` (final), 3600 (settling) or 300 (current) as the
TTL.

- [ ] **Step 1: Write failing tests** with a fake `http` that serves the Task 3 fixtures and counts calls by path, a real `Cache` with a fake clock, and an injectable `today`:

```python
def test_week_state_current():                       # week == current → "current"
def test_week_state_boundary():  # end=2026-11-09 → today 11-12 "settling"; 11-13 "final"
def test_pacific_today_uses_la_date():               # 2026-11-13T07:30Z → date(2026,11,12)
def test_calendar_failure_means_not_final():         # http raises on game_weeks → "settling"; next call retries calendar
def test_calendar_fetched_once():                    # many week_state calls → 1 game_weeks get
def test_final_week_cached_forever():                # final week_stats twice, clock +1 year → 1 get
def test_settling_week_ttl_one_hour():               # clock +3601 → 2 gets
def test_week_fetched_while_settling_becomes_final_later():  # fetch on 11-12, advance today to 11-13 and clock past 3600 → refetch, then result.final True
def test_league_and_season_ttl_five_minutes():       # clock +301 → refetch
def test_format_error_serves_stale():                # second fetch returns {} → stale True with old data
```

- [ ] **Step 2: Run** `../.venv/bin/pytest tests/test_yahoo_client.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `YahooClient`.**
- [ ] **Step 4: Run the tests again.** Expected: all PASS.
- [ ] **Step 5: Commit** `feat(backend): add Yahoo client with current/settling/final caching`.

---

### Task 7: Flask API, logging and app factory

**Files:**
- Create: `backend/app/api.py`, `backend/app/logging_setup.py`, `backend/tests/test_api.py`
- Modify: `backend/app/__init__.py`

**Interfaces:**
- Consumes: `Settings`, `load_settings`, `CATEGORIES`, `YahooClient`, `WeekState`, `build_rankings`, `YahooUnavailable`
- Produces:
  - `create_app(*, settings: Settings | None = None, client: YahooClient | None = None, static_dir: Path | None = None) -> Flask`. With no arguments it calls `load_settings()`, `configure_logging()` and builds `YahooHttp` + `Cache` + `YahooClient`. `static_dir` defaults to `<repo>/frontend/dist`.
  - The endpoints, JSON shapes and headers from §5.5, implemented exactly as written there.

Notes:
- `week` may be `current` or an int. 404 when `n < start_week` or `n > current_week`, and when the value is non-numeric.
- `stale` is true if the league or the stats result was stale.
- `refresh=1` refreshes the stats call only.
- `fetched_at` comes from the stats result, as ISO-8601 UTC with a `Z` suffix.
- The `categories` array comes from `CATEGORIES`: `{"key", "higher_is_better"}` plus `"detail_label"` when set.
- Unknown `/api/...` paths return 404 JSON.
- Non-API paths serve the file from `static_dir` if it exists, otherwise `index.html`. If `static_dir` has no `index.html`, return 404 JSON.
- Error handlers: `YahooUnavailable` → 503 `{"error": "yahoo_unavailable", "message"}`; other exceptions → log with stack trace and return 500 `{"error": "internal", "message": "Internal error"}`.
- `configure_logging()` writes one JSON object per line to stdout: `severity`, `message`, `time`, plus any `extra` fields.

- [ ] **Step 1: Write failing tests** using a `FakeClient` with settable return values/exceptions and a `tmp_path` static dir containing `index.html` and `assets/app.js`:

```python
def test_healthz():                       # 200, body "ok", both headers no-store, client not called
def test_league_shape():                  # keys name,current_week,start_week,end_week,categories; "public, max-age=60" / CDN "max-age=60"
def test_season_rankings_shape():         # scope "season", week None, 9 categories, teams rows; same headers as league
def test_current_week_resolves_number():  # /week/current → week == league.current_week; max-age=60 / CDN 60
def test_week_cache_headers_by_state():   # settling → max-age=300 / CDN max-age=3600; final → max-age=86400 / CDN max-age=31536000
def test_stale_and_errors_not_cached():   # stale response and 503/404/500 → both headers no-store
def test_refresh_passes_flag_and_no_store():  # ?refresh=1 → client.week_stats called with refresh=True; both no-store
def test_out_of_range_week_404():         # current_week+1, start_week-1 and "abc" → 404 {"error": "not_found"}
def test_week_one_has_no_previous():      # current_week=1 → /week/0 is 404; /week/current 200
def test_yahoo_unavailable_503_json():    # client raises → 503, error == "yahoo_unavailable"
def test_stale_flag_propagates():         # league stale → response stale True
def test_unexpected_error_500_json():     # client raises RuntimeError → 500 JSON, not HTML
def test_unknown_api_path_404_json():
def test_spa_fallback_and_static_file():  # /some/page → index.html; /assets/app.js → the file
def test_fetched_at_iso_utc():            # matches r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$"
```

- [ ] **Step 2: Run** `../.venv/bin/pytest tests/test_api.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `api.py`, `logging_setup.py` and `create_app`.**
- [ ] **Step 4: Run the full backend suite** with `../.venv/bin/pytest -v`. Expected: all PASS.
- [ ] **Step 5: Smoke-test against live Yahoo.** Run `set -a; source .env; set +a; cd backend && ../.venv/bin/flask --app app:create_app run --port 8080`, then `curl -s localhost:8080/api/rankings/week/current | head -c 400` and `curl -s localhost:8080/api/league`. Expected: real JSON matching §5.5, and JSON log lines on stdout.
- [ ] **Step 6: Update `docs/api.md`** if anything differs from the implementation, and remove its "Not yet implemented" banner.
- [ ] **Step 7: Commit** `feat(backend): add JSON API, logging and app factory`.

---

### Task 8: Frontend scaffold, API layer and styles

**Files:**
- Create: `frontend/` via `npm create vite@latest frontend -- --template react-ts`, then `frontend/src/api.ts`, `frontend/src/hooks/useApi.ts`, `frontend/src/styles.css`, `frontend/src/test/setup.ts`, `frontend/src/api.test.ts`, `frontend/public/halo_ball.png` (moved from `static/`), `frontend/public/header-left.jpg`, `frontend/public/header-right.jpg`
- Modify: `frontend/vite.config.ts` (dev proxy `/api` and `/healthz` → `http://localhost:8080`; Vitest `environment: "jsdom"`, `setupFiles`), `frontend/package.json` (scripts `test: vitest run`, `typecheck: tsc -b --noEmit`), `frontend/index.html` (title "Mutombo's Heavenly Data", favicon `/halo_ball.png`, the Google Fonts link from the template)
- Delete: the Vite demo assets and CSS (`App.css`, `index.css`, `assets/react.svg`, `public/vite.svg`)

**Interfaces:**
- Produces (`api.ts`):

```ts
export type Category = { key: string; higher_is_better: boolean; detail_label?: string };
export type StatCell = { value: number | null; rank: number; detail?: string };
export type TeamRow = { name: string; avg_rank: number; place: number; stats: Record<string, StatCell> };
export type Rankings = { scope: "week" | "season"; week: number | null; fetched_at: string;
  stale: boolean; refresh_throttled: boolean; categories: Category[]; teams: TeamRow[] };
export type League = { name: string; current_week: number; start_week: number; end_week: number; categories: Category[] };
export class ApiError extends Error { status: number }
export function getLeague(opts?: { refresh?: boolean }): Promise<League>;
export function getSeason(opts?: { refresh?: boolean }): Promise<Rankings>;
export function getWeek(week: number | "current", opts?: { refresh?: boolean }): Promise<Rankings>;
```

- `useApi<T>(load: (refresh: boolean) => Promise<T>, deps: unknown[]): { data: T | undefined; error: ApiError | Error | undefined; loading: boolean; refreshing: boolean; reload: (refresh?: boolean) => Promise<void> }`

- [ ] **Step 1: Scaffold and install** `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom` and `@testing-library/user-event` as dev dependencies. Commit the lockfile.
- [ ] **Step 2: Extract the two header images.** Decode the base64 `src` of the `<img>` tags at `templates/table_view_fancy.html:394` and `:401` into `header-left.jpg` and `header-right.jpg`. Both are JPEG data, even though the second is labeled `image/png`.
- [ ] **Step 3: Port the template's `<style>` block** into `styles.css` unchanged, except remove rules that only served the pandas table post-processing script and add `.medal-gold/.medal-silver/.medal-bronze` classes using the existing `--gold-bg`/`--silver-bg`/`--bronze-bg` variables (the classes the script assigned today).
- [ ] **Step 4: Write failing tests** in `api.test.ts` with `fetch` mocked:

```ts
it("getWeek builds the URL and refresh flag")   // getWeek(7,{refresh:true}) → fetch("/api/rankings/week/7?refresh=1")
it("getWeek('current')")                       // → "/api/rankings/week/current"
it("non-2xx throws ApiError with status")       // 503 body {error,message} → ApiError.status 503, message from body
it("network failure throws Error")
```

- [ ] **Step 5: Run** `cd frontend && npm test`. Expected: FAIL.
- [ ] **Step 6: Implement `api.ts` and `useApi.ts`.**
- [ ] **Step 7: Run** `npm test && npm run typecheck`. Expected: PASS.
- [ ] **Step 8: Commit** `feat(frontend): scaffold Vite React app with typed API layer and ported styles`.

---

### Task 9: Frontend components and page

**Files:**
- Create: `frontend/src/components/{Header,RankingsSection,RankingsTable,RankCell}.tsx`, `frontend/src/components/RankCell.test.tsx`, `frontend/src/components/RankingsTable.test.tsx`, `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/main.tsx` (import `styles.css`)

**Interfaces:**
- Consumes: `api.ts` types and functions, `useApi`
- Produces:
  - `Header({ fetchedAt?: string; stale: boolean })`. Shows "Last updated: <date/time>" formatted with `Intl.DateTimeFormat("en-US", { timeZone: "America/Los_Angeles", weekday: "short", month: "short", day: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short" })`, and "Showing data as of <same format> (Yahoo unavailable)" when `stale` is true.
  - `RankingsSection({ title: string; state: { data?: Rankings; error?: Error; loading: boolean }; onRetry: () => void; actions?: ReactNode; showLegend?: boolean })`
  - `RankingsTable({ rankings: Rankings })`
  - `RankCell({ cell: StatCell; percent?: boolean })`. Shows the value, with percentages written as `.482` (3 decimals, no leading zero) and "–" for null. Medal class by rank 1/2/3. The detail sits underneath when present.
- `App` markup and class names follow `templates/table_view_fancy.html` lines 388-461: eyebrow, header with both images, "Week N" section with Refresh button and legend, "Full Season" section, then "Week N-1" only when `current_week > start_week`.
- Refresh reloads league, current week, season and last week with `refresh=true`. While running it shows the spinner class from the template. When every response has `refresh_throttled`, it shows "Just refreshed" for 3 s.
- Loading: a skeleton block per section. Errors: a card with the message and a "Try again" button that calls `reload()`.

- [ ] **Step 1: Write failing tests:**

```tsx
// RankCell.test.tsx
it("applies medal classes for ranks 1-3 only")     // 1→medal-gold, 2→medal-silver, 3→medal-bronze, 4→none
it("renders dash for null")                         // value null → "–"
it("formats percent without leading zero")          // 0.482 → ".482"
it("shows detail when present")                     // "301/624" visible
// RankingsTable.test.tsx
it("renders columns in category order")            // header: Team, Avg Rank, PTS … TO
it("colors avg rank by place")                      // place 1 → medal-gold on avg cell
it("renders team names as text")                    // name "<b>Mutombo's & 🏀</b>" → exact text present, no <b> element created
// App.test.tsx (fetch mocked per URL)
it("shows loading then three sections")             // current_week 7 → "Week 7", "Full Season", "Week 6"
it("hides last week in week 1")                     // current_week == start_week == 1 → no "Week 0"
it("shows error card and retries")                  // 503 then 200 → "Try again" click → data shown
it("shows stale notice")                            // stale true → "Showing data as of"
it("refresh sends refresh=1")                       // click Refresh → fetch called with "?refresh=1"
```

- [ ] **Step 2: Run** `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement the components and `App`.**
- [ ] **Step 4: Run** `npm test && npm run typecheck && npm run build`. Expected: PASS, and `frontend/dist/index.html` exists.
- [ ] **Step 5: Visual check against live data.** Run the backend as in Task 7 Step 5 and `npm run dev`. Open the Vite URL at desktop width and at 375 px portrait, and compare with production. Expected: same sections, colors and fonts; the table scrolls inside `.table-wrap` with no horizontal page scroll; the header images hide in portrait as they do today. Report any visual difference to the user rather than guessing.
- [ ] **Step 6: Commit** `feat(frontend): add dashboard components with loading, error, stale and refresh states`.

---

### Task 10: Vercel configuration and preview deployment

Closes spec §10.5. A preview deployment needs a Vercel project linked to the repo. Creating
the project and adding env vars are account actions: **ask the user before Step 3.**

**Files:**
- Create: `vercel.json`, plus `api/index.py` only if Step 2 shows a shim is needed
- Modify: `backend/requirements.txt` (remove `gunicorn`), `docs/deployment.md`
- Delete: `Dockerfile`, `docker-compose.yml`

- [ ] **Step 1: Write `vercel.json`:**
  - `buildCommand`: `cd frontend && npm ci && npm run build`
  - `outputDirectory`: `frontend/dist`
  - The Flask app (`backend/app`, `create_app()`) as a Python 3.12 function, with dependencies from `backend/requirements.txt` and `excludeFiles` covering `backend/tests/**` and `backend/scripts/**`
  - Rewrites: `/api/(.*)` and `/healthz` → the function; `/(.*)` → `/index.html` (static files win first)

  Use the `vercel:vercel-functions` skill's guidance for the Python entrypoint (Services config vs `api/index.py` doing `from app import create_app; app = create_app()` with `backend/` on `sys.path`).
- [ ] **Step 2: Build locally** with `npx vercel@latest build` (after `npx vercel@latest pull --yes` once the project exists, or with `--yes` on an unlinked repo if supported). Expected: build succeeds; `.vercel/output/functions/` contains one Python function and `.vercel/output/static/index.html` exists. Add `.vercel/` to `.gitignore`.
- [ ] **Step 3 (user approval): Link the project and set env vars.** With the user, create or link the Vercel project for this repo (Hobby, production branch `main`). Add the 4 env vars for Production and Preview, with the 3 Yahoo values marked Sensitive. The user enters secret values in the dashboard (or pipes them into `vercel env add` without echoing them), never in chat.
- [ ] **Step 4: Preview deploy and smoke test.** Push `stability-refactor` (**ask the user first**; this branch never deploys to production) or run `npx vercel@latest deploy` (preview). Then check:
  - `curl -fsS <preview>/healthz` returns `ok`
  - `curl -fsS <preview>/api/league` returns league JSON
  - running `curl -sSI <preview>/api/rankings/season` twice shows `x-vercel-cache: HIT` the second time
  - `curl -sSI <preview>/api/rankings/season?refresh=1` shows `no-store` and is not a `HIT`
  - `<preview>/some/deep/link` serves the app

  Expected: all of the above. If the preview is protected by Vercel Authentication, use the `vercel:access-protected-vercel-deployment` skill rather than turning protection off.
- [ ] **Step 5: Remove Docker files and `gunicorn`.** Run the backend suite and `npm run build`. Expected: PASS.
- [ ] **Step 6: Update `docs/deployment.md`** with the final `vercel.json` wiring, and record the entrypoint choice in `docs/decisions.md`.
- [ ] **Step 7: Commit** `build: deploy on Vercel (static frontend + Flask function)`.

---

### Task 11: CI, cleanup and docs

**Files:**
- Create: `.github/workflows/ci.yml`
- Delete: `app.py`, `templates/`, `static/`, `requirements.txt`, `sample_data_table.txt`, `51lCd0RlVSL._AC_.jpg`, `.dockerignore` if present
- Modify: `README.md` (root: one paragraph, plus "see docs/"), `docs/README.md` (status: implemented, pending cutover), `docs/architecture.md` (remove the banner and correct any drift), `docs/deployment.md` (final settings, local dev commands for backend and frontend), `docs/decisions.md` (add any decisions made during implementation)

- [ ] **Step 1: Write `ci.yml`.** Trigger on `push` and `pull_request`. Jobs:
  - `backend`: `actions/setup-python` 3.12, `pip install -r backend/requirements-dev.txt`, `pytest` in `backend/`
  - `frontend`: `actions/setup-node` 22 with npm cache, `npm ci`, `npm run typecheck`, `npm test`, `npm run build` in `frontend/`
- [ ] **Step 2: Delete the old files.** Confirm nothing references them with `grep -rn "templates\|app\.py\|sample_data" --exclude-dir=docs --exclude-dir=node_modules --exclude-dir=.git .`. Expected: no hits outside `docs/`.
- [ ] **Step 3: Run everything locally:** `cd backend && ../.venv/bin/pytest`, and `cd frontend && npm run typecheck && npm test && npm run build`. Expected: all pass.
- [ ] **Step 4: Update the docs** as listed above.
- [ ] **Step 5: Commit** `ci: add GitHub Actions; remove legacy app; update docs`.
- [ ] **Step 6: Push and check CI.** Push the branch (already approved in Task 10 if pushed there; otherwise ask first). Confirm CI is green with `gh run list --branch stability-refactor`, and that the Vercel preview for the latest commit passes the Task 10 Step 4 checks. Pushing a non-`main` branch never deploys to production.

---

### Task 12: Cutover to production (with the user)

Every step here changes production. **Get explicit user approval before each step.**

- [ ] **Step 1: Stop Cloud Build deploys (user approval).** Delete the Cloud Build trigger `aa70e010-fd8a-4564-82a1-365f344f37c4` (global) *before* merging, so the merge doesn't start a Cloud Run build of code that no longer has a Dockerfile. The existing Cloud Run service keeps running untouched.
- [ ] **Step 2: Merge (user approval).** Open a PR from `stability-refactor` (summary plus test results). Once CI is green, the preview has been checked on desktop and phone, and the user approves, merge to `main`. Vercel deploys to production.
- [ ] **Step 3: Smoke test production.** Run the Task 10 Step 4 checks against the production URL and load the page on desktop and phone. If anything fails, roll back with `vercel rollback` and report.
- [ ] **Step 3b: Retire Cloud Run (user approval).** Delete the Cloud Run service `mutombos-heavenly-data` (`us-west1`). Ask whether to also delete the unrelated `helloworld` service and the old images in Artifact Registry; don't delete anything that wasn't explicitly approved.
- [ ] **Step 4: Branch protection (user approval, recommended).** Require the CI checks to pass on `main` before merging.
- [ ] **Step 5: Finalize the docs.** Record the production URL, the project name and the cutover date in `docs/deployment.md` and `docs/decisions.md`, and remove the "Not yet implemented" banners. Commit on a short follow-up branch and open a PR.
