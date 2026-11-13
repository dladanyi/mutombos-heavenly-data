# Past seasons on the Full Season section

**Date:** 2026-11-13 · **Status:** approved 2026-11-13; implemented (plan: `docs/plans/2026-11-13-past-seasons.md`)

## Intent

Let people page back from this season to earlier seasons of the league and see how each one
ended: who won, their final record, the final standings (with gold, silver and bronze for the
top three), and the same stat rankings table the current season has. It answers "who won last
year?" and "did the champion actually lead the categories, or win it in the playoffs?"

## Goals

- **Arrows on Full Season:** ‹ and › on the Full Season header step between seasons. The section
  opens on the current season. While that season is in progress, it looks and behaves exactly
  as it does today.
- **A finished current season shows its final results.** From the end of the playoffs until
  `YAHOO_LEAGUE_ID` changes for the next season (about April to October), the current season
  shows the same final view as a past season (the user's decision). That's when people ask
  who won.
- **What a past season shows:**
  1. A champion line.
  2. A final standings table, with medals for ranks 1–3.
  3. The stat rankings table for that season.
- **No upkeep:** past seasons are discovered automatically. When a new season starts and
  `YAHOO_LEAGUE_ID` is updated (already part of the yearly checklist), the old current season
  becomes a past season without any other change.

## Non-goals

- Seasons the configured Yahoo account can't read. Today that's 2024-25 (league
  `454.l.37383`), which returns HTTP 403 because the account wasn't a member. Reading it with
  another member's credentials is out of scope.
- Matching teams across seasons (team names and owners can change), all-time records, and a
  champions history page.
- Week-by-week data for past seasons (weekly tables, the week picker). That's sub-project 2.

## Anti-goals

- Changing anything about an in-progress current season's view: its data, refresh, live badge
  and "Just refreshed" note.
- Showing two sets of medals on one past-season screen (see Display).
- A past season that's slow or calls Yahoo on every view. Finished seasons never change.

## Constraints

- Vercel Hobby, $0, no database. The server cache is in memory per instance (`cache.py`).
- The repo is public. New fixtures go through the capture script's allowlists (no managers).
- What Yahoo returns (checked live on 2026-11-13):
  - **League metadata:** `season` ("2025") and `renew` (`"466_11070"`, meaning previous league
    `466.l.11070`). The current league's `renew` points to last season. Last season's `renew`
    points to `454_37383`, which returns 403. The account's league list
    (`users;use_login=1/games;game_codes=nba/leagues`) confirms it has only 2025 and 2026.
  - **Finished league:** `is_finished: 1`.
  - **`league/<key>/standings`:** each team has
    `team_standings: {rank, playoff_seed, outcome_totals: {wins, losses, ties, percentage}}`.
    `rank` is the final finish after the playoffs, not the regular-season order. In 2025-26,
    rank 2 was seed 3 and seed 2 finished 4th.
  - **Category records:** `wins`/`losses`/`ties` count categories across the season
    (e.g. 118–60–2).
  - **Season totals include the playoffs.** For a finished league, `teams/stats` totals cover
    every week, including the playoff and consolation weeks (2025-26: playoffs from week 21 of
    23, all 10 teams played weeks 21–23). Checked by summing the weekly stats. The standings'
    W–L–T record covers the regular season only (180 = 20 weeks × 9 categories).
  - **Same stat categories:** 2025-26 has the same 9 ranked categories as 2026-27 (same stat
    ids), so `league/<key>/teams/stats` ranks with the existing `parse_team_stats` and
    `build_rankings`. 10 teams, no null values.
- **403 has two meanings.** Yahoo also returns 403 for a bad credential (see deployment notes).
  A 403 on a previous league only counts as "no access to that season" when the current league
  loaded fine in the same request.

## Approaches considered

- **A. Follow Yahoo's `renew` links (chosen by the user).** The backend walks from the current
  league to each previous league until there's no `renew` or the account gets 403. Nothing to
  maintain, and next season shows up automatically. Costs a little error handling for the 403
  stop.
- **B. Previous leagues listed in config** (e.g. `PREVIOUS_SEASONS = {2025: "466.l.11070"}`).
  Simplest code, but it's one more manual step every season and repeats what Yahoo already
  says.
- **C. Fold past seasons into `/api/rankings/season?season=`.** Rejected: a past season's
  response has a different shape (standings) and different caching (final) from the live
  season, so one endpoint would need branches everywhere.

## Design

### Display (decided with the user)

```
FULL SEASON   ‹  2025-26  ›                         [ Final ]

🏆  Champion: Team Name — 118–60–2 (.661)

 #    Team                 Record        Win %   Seed
 🥇 1  Team Name            118–60–2      .661     1
 🥈 2  Team Name            103–75–2      .578     3
 🥉 3  Team Name             96–81–3      .542     4
    4  Team Name            106–72–2      .594     2
    …

 Stat rankings (same table as today, Avg Rank without medal colours)
```

- **Arrows:**
  - ‹ is disabled on the oldest readable season, › is disabled on the current season.
  - The arrows are hidden when only one season exists or the season list can't be loaded.
    The section then behaves exactly as today.
- **Season label:** "2025-26", built from Yahoo's `season` year Y as `Y-(Y+1 mod 100)`, two
  digits.
- **Badge:** an in-progress current season shows "Season to date", as today. A finished season
  (past, or the current one in the off-season) shows "Final".
- **Champion line:** the standings entry with rank 1, showing its name, record and win %.
- **Standings order:** final rank, so the medals go to the actual playoff finishers. Columns
  are #, Team, Record (W–L–T), Win %, Seed, then (added by the user after the build) Avg Rk,
  Med Rk and one rank column per category, so finish and stat ranks read on one row. Ranks
  1–3 in # get the existing gold, silver and bronze colours. Category rank cells get the
  usual 1st/2nd/3rd-in-stat colours, and Avg/Med Rk stay plain. # and Team are pinned while
  the table scrolls sideways.
- **Medals in a past season's stat table:** the standings carry the medals, and Avg Rank
  shows plain numbers (the user's decision). Per-category cells keep their 1st/2nd/3rd-in-stat
  colours, as in every other table, since that's per-stat highlighting rather than a finish
  medal (my call; see "Calls made").
- **Stat table scope:** a finished season's stat rankings use Yahoo's whole-season totals,
  playoff weeks included (the user's decision; one cached call). The record next to them is
  regular season only, so the stat table gets a small caption: "Season totals, including
  playoffs" (my call, so the two aren't read as the same span).
- **Refresh:** the Refresh button keeps refreshing the in-progress data only. A finished season
  never changes.

### API

- **`GET /api/seasons`** lists readable seasons, newest first:

  ```json
  {"seasons": [
    {"season": 2026, "league_key": "478.l.46425", "current": true, "finished": false},
    {"season": 2025, "league_key": "466.l.11070", "current": false, "finished": true}
  ], "complete": true}
  ```

  - `/api/seasons/<season>` for a season not found while the walk is incomplete returns 503
    (Yahoo unavailable), not 404 (plan decision).
  - `complete: false` means the walk stopped on a Yahoo outage rather than at the end of the
    chain. The list may be missing older seasons, and the response is sent `no-store`.
  - Otherwise it gets the "short" headers (60 s), because it depends on the current league.

- **`GET /api/seasons/<season>`** is for finished seasons: any past season, and the current one
  once Yahoo marks it `is_finished`. It returns 404 for an in-progress current season (which
  keeps using `/api/rankings/season`) and for an unknown or unreadable season.

  ```json
  {
    "season": 2025, "league_key": "466.l.11070",
    "fetched_at": "...", "stale": false,
    "categories": [ ... same as rankings ... ],
    "standings": [
      {"rank": 1, "team_key": "466.l.11070.t.4", "name": "...", "wins": 118, "losses": 60,
       "ties": 2, "percentage": 0.661, "playoff_seed": 1}
    ],
    "teams": [ ... same rows as /api/rankings/season ... ]
  }
  ```

  - `standings` is sorted by `rank`.
  - **Caching:** the final headers (1 day browser, 1 year CDN) apply only when the standings
    and the stats were both fetched as final, the same rule as weeks. A stale response is
    `no-store`.
  - **Unfinished past league:** if a past league somehow isn't `is_finished`, it's still
    served, with the short headers.

### Backend

- **Errors:** a new `YahooAccessDenied(YahooUnavailable)` is raised by `yahoo_http` for HTTP
  403. Existing callers are unaffected, because it's still a `YahooUnavailable`.
- **Parsing:**
  - `LeagueInfo` gains `season: int` and `previous_league_key: str | None` (from `renew`,
    `"466_11070"` → `"466.l.11070"`; empty or missing → None) and `is_finished: bool`.
  - New `parse_standings(payload) -> list[Standing]`, where `Standing` has `rank`, `team_key`,
    `name`, `wins`, `losses`, `ties`, `percentage`, `playoff_seed`.
- **Yahoo client:**
  - `YahooClient.seasons()` starts from the current league and follows
    `previous_league_key`.
  - Each previous league's metadata is cached for 1 day. The cache needs a lifetime before
    the fetch, and this is one small call per league per day (plan decision).
  - On `YahooAccessDenied` for a previous league, the walk stops, and that stop is cached for
    1 day so a later access grant shows up.
  - On any other `YahooUnavailable`, the walk stops with `complete = False` and nothing is
    cached about the stop.
  - The walk is capped at 20 seasons as a loop guard.
- **Finished-season data:**
  - `YahooClient.final_season(key)` returns standings and whole-season team stats for a
    league. Both are cached forever (`ttl=None`) when the league is finished, and with the
    league TTL (5 min) otherwise.
  - Rankings come from the existing `build_rankings`. `place` is still sent, and the frontend
    knows it's showing a past season, so it just doesn't colour Avg Rank.
- **The current league's own fetches are unchanged.**

### Frontend

- `api.ts`: `getSeasons()`, `getFinalSeason(season)` and their types.
- **Full Season section:** holds the selected season. It loads `/api/seasons` once on page
  load and chooses the view by `finished`, not by `current`:
  - an in-progress season gets today's view from `/api/rankings/season`
  - a finished season gets the final view from `/api/seasons/<season>`, fetched when you
    arrive at it (the browser caches it)
  - in the off-season that means the section opens straight on the final view
- **New `StandingsTable` component** with the champion line.
- **`RankingsTable` gets `medals={false}`** to switch off the Avg Rank place colours.
- **Keyboard and screen readers:** the arrows are real buttons with accessible names
  ("Previous season" / "Next season") and are disabled at the ends.

### Fixtures and tests

- **Capture script:**
  - Allowlists for the `standings` league part. Teams keep `team_standings` with only `rank`,
    `playoff_seed` and `outcome_totals`.
  - Add `renew` and `season` to `LEAGUE_META_KEEP`.
  - Capture the previous league's metadata, standings and season stats.
- **Tests:**
  - Parsing: standings, `renew` → key, `is_finished`.
  - The season walk:
    - stops at the end of the chain
    - stops at a 403 (cached) and on an outage (`complete: false`, not cached)
    - respects the loop guard
  - Finished-season caching and API shape:
    - the current season is served once it's finished
    - 404 for an in-progress current season or an unknown season
    - final headers only when both parts are final
  - Frontend: the arrows' enabled and disabled states, hiding the arrows on one season or a
    failed list, the champion line, standings medals, no Avg Rank medals in a finished season,
    the "including playoffs" caption, and a finished current season opening on the final view.

### Docs

- `api.md` (two endpoints)
- `architecture.md`
- `decisions.md` (renew walk, 403 meaning, medals on standings only)
- `deployment.md` "Each new season": note that past seasons appear automatically
- the fixtures README

## Left to the builder

- Exact styling of the champion line and arrows, within the existing visual language
  (Bebas Neue headers, DM Mono numbers, the medal colour variables).
- **Phone layout:** the standings table must work at 390 px with the existing sticky team
  column and in-card scroll.
- Loading and error states for a past season: reuse `RankingsSection`'s skeleton and error card.

## Calls made (not discussed)

- **"Season totals, including playoffs" caption** on a finished season's stat table.
- **Per-category stat colours stay in past seasons.** Only the Avg Rank place medals are off.
- **Season list:** `/api/seasons` is fetched on page load, so the back arrow's state is known
  right away. It's one small request, cached by the CDN for 60 s.
- **Past seasons with different categories:** if a past season ranked different categories,
  a configured category it lacks ranks every team tied (null values). No such season exists
  today.
- **Win % format:** shown as Yahoo's 3-decimal string, e.g. ".661".
