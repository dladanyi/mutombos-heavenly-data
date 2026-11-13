# Past Seasons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ‹ › arrows to Full Season so people can step back to finished seasons. A finished
season shows its champion, its final standings with medals, and its stat rankings. The current
season shows the same final view once it has finished.

**Architecture:** The backend walks Yahoo's `renew` links from the current league to list the
seasons it can read, then serves each finished season's standings plus whole-season stats.
Both are cached forever once final. The frontend's Full Season section gets a season selector.
It picks today's view or the final view by `finished`.

**Tech Stack:** Flask (Python 3, pytest) and React + Vite + TypeScript (vitest, Testing Library).

**Spec:** `docs/specs/2026-11-13-past-seasons-design.md`

## Global Constraints

- Vercel Hobby, $0, no database. The server cache is the in-memory `Cache` (`backend/app/cache.py`).
- The repo is public. Fixtures go only through `capture_fixtures.py` allowlists, with no managers.
- A previous league's HTTP 403 means "no access to that season" (the walk stops). Every other
  `YahooUnavailable` means an outage.
- The walk is capped at 20 seasons.
- **Cache lifetimes:**
  - previous-league metadata: 1 day
  - a 403 stop: 1 day
  - finished-season standings and stats: forever (`ttl=None`)
  - unfinished season data: `CURRENT_TTL` (300 s)
- **Headers:**
  - `/api/seasons` gets "short" headers, or `no-store` when `complete` is false.
  - `/api/seasons/<season>` gets "final" headers only when the season is finished and both
    parts were fetched final. It gets `no-store` when stale and "short" otherwise.
- **Copy:**
  - badge "Final"
  - caption "Season totals, including playoffs"
  - champion line `🏆 Champion: <name> — <W>–<L>–<T> (<.pct>)`
  - season label `2025-26`
  - arrow names "Previous season" / "Next season"
- **Medals:** standings ranks 1–3 get gold, silver and bronze. A finished season's stat table
  has no Avg Rank medals; per-category stat colours stay.
- The current in-progress season's view, refresh, badge and "Just refreshed" behaviour are
  unchanged.

## Review Focus

1. **Yahoo is down while the walk runs on page load** (`complete: false`). The arrows should
   still offer the seasons that were found, and the page must not break. Test in Task 4.
2. **Fast arrow clicks.** A slow response for one season must never show under another
   season's label. Test in Task 4.
3. **A standings entry with an empty `playoff_seed` or `rank`** (Yahoo sends `""` for teams
   that missed the playoffs in some leagues). Parse it as `None`, show "–", and don't crash.
   Test in Task 1.
4. **A malformed season in the URL** (`/api/seasons/abc`, `/api/seasons/2025-26`,
   `/api/seasons/1999`). Return 404 JSON, never a 500. Test in Task 3.
5. **The current season finishes between page loads** (off-season). The section opens on the
   final view, and the Refresh button keeps working for the other sections. Test in Task 4.

---

### Task 1: Access-denied error, league fields, standings parser, fixtures

**Files:**
- Modify: `backend/app/errors.py`, `backend/app/yahoo_http.py` (the final `raise` in `get_json`), `backend/app/parsing.py`
- Modify: `backend/scripts/capture_fixtures.py`, `backend/tests/fixtures/README.md`
- Create (by capture): `backend/tests/fixtures/prev_league.json`, `prev_standings.json`, `prev_season_stats.json`
- Test: `backend/tests/test_yahoo_http.py`, `backend/tests/test_parsing.py`, `backend/tests/test_capture_fixtures.py`

**Interfaces:**
- Produces:
  - `class YahooAccessDenied(YahooUnavailable)`, raised by `YahooHttp.get_json` for HTTP 403
  - `LeagueInfo` gains defaulted fields, so existing positional constructions still work:
    `league_key: str = ""`, `season: int | None = None`, `previous_league_key: str | None = None`,
    `is_finished: bool = False`
  - `@dataclass(frozen=True) class Standing: rank: int | None; team_key: str; name: str; wins: int; losses: int; ties: int; percentage: float | None; playoff_seed: int | None`
  - `parse_standings(payload: dict) -> list[Standing]`, sorted by rank with `None` last

- [ ] **Step 1: Write failing tests**

  `test_yahoo_http.py`:
  - `test_403_raises_access_denied`: the fake session returns 403, and `pytest.raises(YahooAccessDenied)`.
    `YahooAccessDenied` must also be an instance of `YahooUnavailable`.

  `test_parsing.py`:
  - `test_parse_league_season_fields`: `parse_league(load("prev_league.json"))` has
    `season == 2025`, `league_key == "466.l.11070"`, `is_finished is True`, and
    `previous_league_key == "454.l.37383"`.
  - `test_parse_league_renew_empty_or_missing`: `renew` `""` or absent gives `None`.
    `is_finished` absent gives `False`.
  - `test_parse_standings_fixture`:
    - 10 rows, ranks `[1..10]` in order
    - every row has wins + losses + ties == 180
    - row 0 has `playoff_seed == 1` and `percentage == 0.661`
    - names match `^Team \d+$`
  - `test_parse_standings_blank_seed_and_rank`: synthetic `playoff_seed: ""` and `rank: ""`
    give `None`, and that row sorts last.
  - `test_parse_standings_malformed_raises`: a missing `team_standings`, or a non-dict
    `outcome_totals`, raises `YahooFormatError`.

  `test_capture_fixtures.py`:
  - `test_standings_keep_only_allowlisted`: a `standings` league part keeps per team only
    the metadata allowlist plus `team_standings` reduced to
    `{"rank", "playoff_seed", "outcome_totals"}`. Managers and `games_back` are dropped.
  - `test_league_meta_keeps_renew`: `renew` and `season` are kept.

- [ ] **Step 2: Run, expect failures**

  Run: `cd backend && ../.venv/bin/pytest -q tests/test_yahoo_http.py tests/test_parsing.py tests/test_capture_fixtures.py`
  Expected: collection or assert failures (`YahooAccessDenied` and `parse_standings` don't exist yet).

- [ ] **Step 3: Implement**

  - **Errors:** add `YahooAccessDenied` to `errors.py`. `yahoo_http.get_json` raises it
    instead of `YahooUnavailable` when `status == 403`.
  - **League fields:** `parse_league` reads `league_key`, `season` (int), `renew`
    (`"466_11070"` → `"466.l.11070"`) and `is_finished` (`== 1` or `"1"`).
  - **Standings:** add `parse_standings`. It locates `standings` with `_find_dict_with`, then
    `standings[0]["teams"]` via `_indexed`, then each team's metadata via `_team_metadata`
    and `team_standings` from the team's dict parts. Blank strings become `None`.
  - **Capture script:**
    - add `"renew"` to `LEAGUE_META_KEEP`
    - add `TEAM_PARTS_KEEP |= {"team_standings"}`, with a reducer that keeps
      `STANDINGS_KEEP = {"rank", "playoff_seed", "outcome_totals"}`
    - the `standings` league part is rebuilt as `[{"teams": _anonymise_teams(...)}]`
  - **`main()`:** read `renew` from the league metadata and capture `prev_league.json`
    (`league/<prev>`), `prev_standings.json` (`league/<prev>/standings`) and
    `prev_season_stats.json` (`league/<prev>/teams/stats`). Skip all three if there's no `renew`.

- [ ] **Step 4: Re-capture and check for personal data**

  Run: `set -a; source .env; set +a; .venv/bin/python backend/scripts/capture_fixtures.py`
  Then: `grep -ciE 'manager|email|guid|nickname|logo|url' backend/tests/fixtures/prev_*.json`
  Expected: 0 for each file. Names are only `Team N` plus the league name.

- [ ] **Step 5: Run all backend tests, expect a pass**

  Run: `cd backend && ../.venv/bin/pytest -q`
  Expected: all pass. If the re-capture moved the current week, the existing tests derive
  their constants from the fixtures. Fix only the pinned calendar dates if needed.

- [ ] **Step 6: Update the fixtures README** (the new files and the standings allowlist), then commit.

  ```bash
  git add backend && git commit -m "feat: parse standings and league renew; 403 is access denied"
  ```

### Task 2: Season walk and finished-season data in YahooClient

**Files:**
- Modify: `backend/app/yahoo_client.py`
- Test: `backend/tests/test_yahoo_client.py` (extend `FakeHttp` with `league/466.l.11070` →
  `prev_league.json`, `/standings` → `prev_standings.json`, `/teams/stats` →
  `prev_season_stats.json`, and `league/454.l.37383` raising `YahooAccessDenied`)

**Interfaces:**
- Consumes: `LeagueInfo` (with the new fields), `parse_league`, `parse_standings`,
  `parse_team_stats`, `YahooAccessDenied` (Task 1)
- Produces:
  - `@dataclass(frozen=True) class SeasonRef: season: int; league_key: str; current: bool; finished: bool`
  - `YahooClient.seasons(refresh: bool = False) -> tuple[list[SeasonRef], bool, list[CacheResult]]`:
    newest first, then `complete`, then every `CacheResult` used (for stale and headers)
  - `YahooClient.final_season(league_key: str, finished: bool, refresh: bool = False) -> tuple[list[Standing], list[TeamStats], CacheResult, CacheResult]`
    (standings and its result, then stats and its result)

- [ ] **Step 1: Write failing tests**
  - `test_seasons_walks_renew_chain`: returns `[2026 current, 2025 finished]` with `complete is True`.
    `http.calls["league/454.l.37383"] == 1`.
  - `test_seasons_access_denied_stop_cached_one_day`: a second call within 86399 s doesn't
    re-request `454.l.37383`. After 86401 s it does.
  - `test_seasons_outage_marks_incomplete_and_is_not_cached`: with `466.l.11070` failing via
    `YahooUnavailable`, the result is `[2026]` with `complete is False`. Recover the path,
    advance the clock past the 30 s failure cooldown, call again, and get two seasons.
  - `test_seasons_loop_guard`: a self-referencing `renew` override stops at 20 entries.
  - `test_final_season_finished_cached_forever`: two calls 365 days apart cause one standings
    call and one stats call. Both results are `final`.
  - `test_final_season_unfinished_uses_current_ttl`: `finished=False` refetches after 301 s.

- [ ] **Step 2: Run, expect failures**

  Run: `cd backend && ../.venv/bin/pytest -q tests/test_yahoo_client.py`
  Expected: `AttributeError` (no `seasons`).

- [ ] **Step 3: Implement**

  - **Current league:** `seasons()` uses `self.league(refresh)` for the current league.
  - **Previous leagues:** each previous league's metadata goes through
    `self._fetch(f"league/{key}", parse_or_none, 86400, refresh)`, where `parse_or_none` wraps
    the HTTP call and returns `None` on `YahooAccessDenied`. That caches the 403 stop for a
    day. Write it as a small closure in `seasons()`, not in `_fetch`.
  - **Outages:** on any other `YahooUnavailable`, set `complete = False` and stop.
  - **Finished-season data:** `final_season` fetches `league/<key>/standings` and
    `league/<key>/teams/stats` with `ttl=None if finished else CURRENT_TTL`.

- [ ] **Step 4: Run, expect a pass**

  Run: `cd backend && ../.venv/bin/pytest -q`

- [ ] **Step 5: Commit**

  ```bash
  git add backend && git commit -m "feat: walk past seasons and fetch final standings"
  ```

### Task 3: `/api/seasons` and `/api/seasons/<season>`

**Files:**
- Modify: `backend/app/api.py`
- Test: `backend/tests/test_api.py` (`FakeClient` gains `seasons()` and `final_season()`,
  returning configurable data)

**Interfaces:**
- Consumes: `SeasonRef`, `seasons()`, `final_season()` (Task 2), `build_rankings`, `_categories`, `_respond`
- Produces (the JSON the frontend relies on):
  - `/api/seasons`: `{"seasons": [{"season", "league_key", "current", "finished"}], "complete"}`
  - `/api/seasons/<season>`:
    `{"season", "league_key", "fetched_at", "stale", "categories", "standings": [{"rank", "team_key", "name", "wins", "losses", "ties", "percentage", "playoff_seed"}], "teams": [...rankings rows]}`

- [ ] **Step 1: Write failing tests**
  - `test_seasons_list_shape_and_short_headers`
  - `test_seasons_list_incomplete_is_no_store`
  - `test_past_season_body`:
    - standings sorted by rank, with the exact keys above
    - `teams` has the rankings rows
    - `fetched_at` is the standings result's time
  - `test_past_season_final_headers_only_when_both_final`: final + final gives
    `("public, max-age=86400", "max-age=31536000")`. One part non-final gives the short headers.
  - `test_current_in_progress_season_404`, and
    `test_current_finished_season_served` (current and `finished=True` gives 200)
  - `@pytest.mark.parametrize("season", ["abc", "2025-26", "1999", "-1"]) test_bad_season_404`:
    404 with `{"error": "not_found"}`
  - `test_unknown_season_while_incomplete_503`
  - `test_stale_season_no_store`

- [ ] **Step 2: Run, expect failures**

  Run: `cd backend && ../.venv/bin/pytest -q tests/test_api.py`

- [ ] **Step 3: Implement both routes in `api.py`**

  - Parse `<season>` with `str.isdecimal()`; otherwise return 404.
  - Look the season up in `seasons()`.
  - If it isn't found: raise `YahooUnavailable` when `complete` is false, otherwise 404.
  - Pass every `CacheResult` (walk, standings, stats) to `_respond` so staleness forces
    `no-store`.

- [ ] **Step 4: Run, expect a pass, then commit**

  Run: `cd backend && ../.venv/bin/pytest -q`

  ```bash
  git add backend && git commit -m "feat: seasons API"
  ```

### Task 4: Full Season arrows, standings table and final view

**Files:**
- Modify: `frontend/src/api.ts`, `frontend/src/App.tsx`, `frontend/src/components/RankingsTable.tsx`, `frontend/src/styles.css`, `frontend/src/test/data.ts`
- Create: `frontend/src/components/FullSeasonSection.tsx`, `frontend/src/components/StandingsTable.tsx`
- Test: `frontend/src/components/StandingsTable.test.tsx`, `frontend/src/components/FullSeasonSection.test.tsx`, `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: the Task 3 JSON
- Produces:
  - **Types:** `SeasonRef`, `SeasonsList = { seasons: SeasonRef[]; complete: boolean }`,
    `Standing`, and `FinalSeason = Omit<Rankings, 'scope' | 'week' | 'state' | 'refresh_throttled'> & { season: number; league_key: string; standings: Standing[] }`
  - **API calls:** `getSeasons(): Promise<SeasonsList>`, `getFinalSeason(season: number): Promise<FinalSeason>`
  - **Helpers:** `seasonLabel(year: number): string`, e.g. `seasonLabel(2025) === '2025-26'`
    and `seasonLabel(2099) === '2099-00'`. Put it in `api.ts` next to the types.
  - `RankingsTable` gains `medals?: boolean` (default `true`). When false, Avg Rank keeps
    class `avg-rank` and gets no `medal-*` class.
  - **Components:**
    - `StandingsTable({ standings }: { standings: Standing[] })` renders the champion line and
      the table.
    - `FullSeasonSection({ current, onRetry }: { current: ApiState<Rankings>; onRetry: () => void })`
      replaces the Full Season `RankingsSection` in `App.tsx`. `App` keeps owning the current
      season's `useApi`, so `refreshAll` and the "Just refreshed" logic stay unchanged.

- [ ] **Step 1: Write failing tests**

  `StandingsTable.test.tsx`:
  - The champion line text is exactly `🏆 Champion: Team 4 — 118–60–2 (.661)`.
  - The header is `['#', 'Team', 'Record', 'Win %', 'Seed']`.
  - Ranks 1, 2 and 3 have the `medal-gold`, `medal-silver` and `medal-bronze` classes on the
    rank cell. Rank 4 has none.
  - A `null` seed shows `–`.

  `FullSeasonSection.test.tsx` (mock `fetch` the way `App.test.tsx` does):
  - Opens on the current in-progress season: the title shows the label, the badge reads
    "Season to date", "Previous season" is enabled, and "Next season" is disabled.
  - Clicking "Previous season":
    - the label becomes `2025-26` and the badge reads "Final"
    - the standings table and the caption "Season totals, including playoffs" are shown
    - the stat table has no `medal-` class on any `td.avg-rank`
    - "Previous season" is now disabled
  - The arrows are hidden when `/api/seasons` returns one season, and when it fails (500).
    The current table still renders.
  - `complete: false` with two seasons still enables "Previous season" (Review Focus 1).
  - Fast clicks: with the 2025 response delayed, click back and then forward. The current
    season's table shows and no standings table renders (Review Focus 2).
  - The current season with `finished: true` opens on the final view: badge "Final", standings
    shown, and `/api/seasons/2026` requested (Review Focus 5).

  `App.test.tsx`: add `/api/seasons` to `happyRoutes()`. Add a test that the Refresh button
  still sends `/api/rankings/season?refresh=1` while the section shows a finished current
  season.

- [ ] **Step 2: Run, expect failures**

  Run: `cd frontend && npx vitest run`

- [ ] **Step 3: Implement**

  - **`FullSeasonSection`:**
    - holds `index` (0 = newest)
    - loads seasons with `useApi(() => getSeasons(), [])`
    - loads the selected finished season with
      `useApi(() => finished ? getFinalSeason(year) : Promise.resolve(undefined), [year, finished])`
      (`useApi` already drops out-of-order responses and clears data when `deps` change)
    - the arrows sit in `RankingsSection`'s `actions` slot
    - the final view reuses `RankingsSection`'s skeleton and error-card pattern
  - **Styles:** use the existing tokens and medal classes. The arrow buttons look like
    `.refresh-btn`. Keep the phone layout at 390 px with the sticky team column.

- [ ] **Step 4: Run, expect a pass. Typecheck and build.**

  Run: `cd frontend && npx vitest run && npm run typecheck && npm run build`

- [ ] **Step 5: Commit**

  ```bash
  git add frontend && git commit -m "feat: full season arrows with final standings"
  ```

### Task 5: Docs, manual check, PR

**Files:**
- Modify: `docs/api.md` (two endpoints, the headers rows, the 503 rule), `docs/architecture.md`
  (`yahoo_client` and `parsing` rows, the new components), `docs/decisions.md`
  (renew walk, 403 meaning, medals on standings only, whole-season totals,
  the off-season final view), `docs/deployment.md` ("Each new season": past seasons appear
  automatically, and a 403 on an older league is expected)
- Add: the spec (`docs/specs/2026-11-13-past-seasons-design.md`) and this plan, if not yet committed

- [ ] **Step 1: Update the docs listed above, run `graphify update .`, and commit.**
- [ ] **Step 2: Manual check against live data**

  Run the local Flask app on port 8080 and Vite on port 5173 (`docs/deployment.md` "Local
  development"). At 1440 px and 390 px, check:
  - stepping back to 2025-26 shows the champion line, the medals on ranks 1–3, the caption,
    and plain Avg Rank
  - stepping forward restores today's view
  - no page-level horizontal overflow
  - no console errors
- [ ] **Step 3: Push the branch and open the PR**

  Run `/code-review`, post the review as mutombot (`scripts/gh-as-reviewer.sh`), fix, and
  wait for CI to go green. Merge only when the user says so.
