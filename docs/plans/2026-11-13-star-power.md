# Star Power Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Star Power tab. It ranks teams by how many of their players are in Yahoo's
season-to-date top 10, 25 and 50, and lists those players.

**Architecture:** A new `/api/stars` endpoint fetches Yahoo's top 50 (two pages, with
ownership), cached for 1 hour. Plain-Python `stars.py` groups the players by team and orders
the teams. On the frontend, a hash-based tab bar switches between the existing rankings and a
new Star Power section.

**Tech Stack:** Flask (pytest) and React + Vite + TypeScript (vitest).

**Spec:** `docs/specs/2026-11-13-star-power-design.md`

## Global Constraints

- **Team order:** top-10 count, then top-25, then top-50 (all descending), then name. Counts
  are cumulative. `place` uses min-tie on the (top10, top25, top50) tuple.
- **Rank:** `start + index + 1` from `players;sort=AR;sort_type=season;start=N;count=25/ownership`,
  with N = 0 and N = 25.
- **Cache:** server TTL 3600 s. Headers are browser `public, max-age=300` and CDN `max-age=3600`.
  `?refresh=1` and stale responses are sent `no-store`. The refresh throttle is the existing
  cache's 30 s.
- **Public repo:** player fixtures keep only `player_key`, `player_id`, `name`,
  `editorial_team_abbr` and `display_position`, plus `ownership` reduced to
  `{ownership_type, owner_team_key}`.
- **Copy:**
  - tabs "Rankings" and "Star Power"; hash `#stars`
  - section title "Star Power", badge "Season to date · top 50"
  - columns `#`, `Team`, `Top 10`, `Top 25`, `Top 50`
  - "Not on a team:" for unowned players; "No top-50 players" for a team without any
  - ★ before top-10 players
  - FA = free agent, W = waivers

## Review Focus

1. **Fewer than 50 ranked players come back** (a short second page, or an empty page early in
   the season). Rank what came back, and don't crash. Test in Task 1.
2. **A top-50 player owned by a team key that isn't in the season stats** (a mid-season team
   change). Don't drop him silently: list him under "Not on a team". Test in Task 2.
3. **Yahoo fails on the second page only.** Return 503 (or stale), never a half list cached
   for an hour. Test in Task 2.
4. **An unknown hash, or `#stars` on load.** Open the right tab, and Back/Forward switch tabs.
   Test in Task 3.
5. **All teams tied** (e.g. no top-50 players anywhere). Every team gets place 1 and no crash.
   Test in Task 2.

---

### Task 1: Ranked-player parser and fixture capture

**Files:** `backend/app/parsing.py`, `backend/scripts/capture_fixtures.py`, `backend/tests/fixtures/README.md`,
new fixtures `top_players_0.json` and `top_players_25.json`; tests in `test_parsing.py` and `test_capture_fixtures.py`.

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class RankedPlayer: rank: int; player_key: str; name: str; nba_team: str; position: str; ownership_type: str; owner_team_key: str | None`
  - `parse_ranked_players(payload: dict, start: int) -> list[RankedPlayer]`

- [ ] **Step 1: Write failing tests**
  - `test_parse_ranked_players_fixture`: `top_players_0.json` with `start=0` gives 25 players
    with ranks 1..25. Every `ownership_type` is in {"team", "freeagents", "waivers"}. `team`
    implies an `owner_team_key`.
  - `test_parse_ranked_players_offsets_rank`: `top_players_25.json` with `start=25` gives a
    first rank of 26.
  - `test_parse_ranked_players_empty_or_short`: an empty `players` (`[]` or missing) gives
    `[]`. A 3-player page gives ranks start+1..start+3 (Review Focus 1).
  - `test_parse_ranked_players_malformed_raises`: a missing `name` or `player_key` raises
    `YahooFormatError`.
  - Capture: `test_players_keep_only_allowlisted`. Headshot, URLs and notes are dropped, and
    `ownership` keeps only `ownership_type` and `owner_team_key`.
- [ ] **Step 2: Run them and expect failures**
  Run: `cd backend && ../.venv/bin/python -m pytest -q`
- [ ] **Step 3: Implement**
  - The parser reads metadata through `_merged_metadata` and ownership from the player's
    dict parts.
  - The capture script gets a `players` league-part allowlist: `PLAYER_META_KEEP` and
    `OWNERSHIP_KEEP`.
  - `main()` captures both pages.
- [ ] **Step 4: Re-capture, check for personal data, run all tests**
  - Check: grep `manager|email|guid|nickname|logo|url|headshot` in `top_players_*.json`
    gives 0.
- [ ] **Step 5: Update the fixtures README and commit**
  `feat: parse Yahoo's season-to-date player ranks`

### Task 2: Grouping, client and `/api/stars`

**Files:** new `backend/app/stars.py`; `backend/app/yahoo_client.py`, `backend/app/api.py`;
new test file `test_stars.py`; tests in `test_yahoo_client.py` and `test_api.py`.

**Interfaces:**
- Consumes: `RankedPlayer` and `parse_ranked_players` (Task 1), and `TeamStats` from
  `season_stats()`.
- Produces:
  - `LEVELS = (10, 25, 50)`
  - `build_star_power(players: list[RankedPlayer], teams: list[TeamStats]) -> dict` returns
    `{"teams": [...], "unowned": [...]}` (row shapes as in the spec's JSON)
  - `YahooClient.top_players(refresh: bool = False) -> tuple[list[RankedPlayer], CacheResult]`
  - The `GET /api/stars` body is as in the spec.

- [ ] **Step 1: Write failing tests**
  - `test_stars.py`:
    - `test_counts_are_cumulative_and_order_is_top10_then_25_then_50`
    - `test_ties_share_place_and_sort_by_name`
    - `test_team_without_stars_listed_with_zero_counts`
    - `test_players_listed_in_rank_order_per_team`
    - `test_unowned_and_unknown_owner_go_to_unowned`: free agents, waivers, and a team key
      not in `teams` (Review Focus 2)
    - `test_all_teams_tied_share_place_one` (Review Focus 5)
  - `test_yahoo_client.py`:
    - `test_top_players_two_pages_cached_one_hour`: 50 players with ranks 1..50, and both
      paths called once within 3599 s and again after 3601 s
    - `test_top_players_second_page_failure_not_cached`: page 25 fails, so
      `YahooUnavailable` is raised. On recovery, after the 30 s cooldown, both pages are
      fetched (Review Focus 3).
  - `test_api.py`:
    - `test_stars_body_and_headers`: shape, `levels`, and headers
      `("public, max-age=300", "max-age=3600")`
    - `test_stars_refresh_and_stale_no_store`
    - `test_stars_yahoo_down_503`
- [ ] **Step 2: Run them and expect failures**
- [ ] **Step 3: Implement**
  - **`top_players`:** fetches both pages inside a single cached fetch (key
    `"<league>/players:top50"`, TTL 3600 s), so a failure on either page caches nothing.
  - **`/api/stars`:** uses `season_stats()` for the team list and passes both `CacheResult`s
    to `_respond`.
  - **Header kind:** add a new header kind, `"stars": ("public, max-age=300", "max-age=3600")`.
- [ ] **Step 4: Run all backend tests, then commit**
  `feat: star power API`

### Task 3: Tabs and the Star Power screen

**Files:** `frontend/src/api.ts`, `frontend/src/App.tsx`, `frontend/src/styles.css`, `frontend/src/test/data.ts`;
new components `TabBar.tsx`, `StarPowerSection.tsx` and `StarPowerTable.tsx`; tests in
`StarPowerTable.test.tsx` and `App.test.tsx`.

**Interfaces:**
- Consumes: the `/api/stars` JSON.
- Produces:
  - types `StarPlayer`, `StarTeam` and `StarPower`, and `getStars(opts?: { refresh?: boolean }): Promise<StarPower>`
  - `StarPowerTable({ data }: { data: StarPower })`

- [ ] **Step 1: Write failing tests**
  - `StarPowerTable.test.tsx`:
    - header `['#', 'Team', 'Top 10', 'Top 25', 'Top 50']`
    - medal classes on places 1–3
    - the player line text `★ 1 Victor Wembanyama SAS C` for a top-10 player, and no ★ for
      rank 14
    - "No top-50 players" for an empty team
    - the line "Not on a team: 37 Player X (FA) · 48 Player Y (W)"
  - `App.test.tsx`:
    - The Rankings tab is selected by default, and `/api/stars` is not requested.
    - Clicking Star Power sets `location.hash === '#stars'`, requests `/api/stars` and shows
      the table.
    - Loading with `#stars` opens Star Power.
    - A `hashchange` back to `''` shows Rankings (Review Focus 4).
- [ ] **Step 2: Run them and expect failures**
- [ ] **Step 3: Implement**
  - **Tab state:** `App` holds `tab: 'rankings' | 'stars'`, read from `location.hash` and
    kept in sync with a `hashchange` listener. Clicking a tab sets `location.hash`.
  - **Star Power data:** `StarPowerSection` uses `useApi` for `getStars`, mounted only when
    its tab is active. It reuses the section and badge styles, plus a Refresh button.
  - **Styles:** the tab bar uses existing tokens. The player line wraps, and the table
    scrolls inside its card with Team pinned.
- [ ] **Step 4: Run vitest, typecheck and build, then commit**
  `feat: star power tab`

### Task 4: Docs, manual check, PR

- [ ] **Step 1: Update the docs**
  - `docs/api.md`: the endpoint and its headers row
  - `docs/architecture.md`: `stars.py`, the parsing and client rows, the tabs and components
  - `docs/decisions.md`: the ordering rule, cumulative counts, the 1-hour cache, and why tabs
    with a hash
  - mark the spec status as implemented
  - then run `graphify update .` and commit
- [ ] **Step 2: Manual check**
  Check at 1440 and 390 px against live data:
  - the tab switch, the counts and medals, the player lines, "Not on a team"
  - Back from `#stars` goes to Rankings
  - no console errors and no page-level horizontal overflow
- [ ] **Step 3: Push, open the PR, run `/code-review`, post it as mutombot, fix, CI green**
  Merge only when the user says so.
