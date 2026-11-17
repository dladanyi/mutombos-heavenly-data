# All-Play

**Date:** 2026-11-16 · **Status:** design, awaiting approval · **Size:** project (full design)

## Intent

Average rank can flatter a team that wins one category by a mile and loses the rest narrowly.
What actually wins a head-to-head categories week is taking more categories than the opponent.
All-Play plays every team against every other team, every week, and asks: on average, how many
categories would this team have won? The team that wins the most categories on average was the
best team that week. Summed over the season, the all-play record shows who has really been best,
and set against the real standings it shows who has been lucky or unlucky with their schedule.

## Goals

- A new **All-Play** tab (`#allplay`) with three parts, top to bottom:
  1. **Week all-play standings**: for one week, each team's average categories won per opponent
     (**Avg Cats**), its all-play matchup record (**W–L–T**) and **Win %**, plus its real
     matchup that week.
  2. **Week head-to-head grid**: every pairing of teams that week, as the row team's category
     W–L–T against the column team.
  3. **Season all-play standings**: the weekly all-play results summed over the completed weeks
     of the current season, ranked by Win %.
- The week shown follows the same ‹ › week arrows as the Rankings tab.
- No new Yahoo calls for the week view; the season view reuses the cached week totals.

## Non-goals

- Past seasons (2025-26) in the All-Play tab. The season arrows are not added here.
- Excluding playoff weeks from the season totals (see "Calls made" below).
- Changing anything on the Rankings or Star Power tabs, apart from sharing the chosen week.

## Anti-goals

- Two definitions of "who wins a category". The scoring lives in Python only; the frontend
  only displays numbers.
- A season record that silently skips a week Yahoo failed to return.

## Scoring rules (user-agreed unless marked)

For one week, compare every ordered pair of distinct teams (A, B), category by category, over
the 9 ranked categories in `config.CATEGORIES`, using the parsed numeric values
(`rankings.to_number`, the same values the rankings use):

- Higher value wins; for TO (`higher_is_better=False`) the lower value wins.
- Equal values tie.
- A team with a value beats a team with `None`; two `None`s tie. (Matches the rankings rule
  that a missing value ranks last.)

From A's side this gives `cats_won`, `cats_lost`, `cats_tied` against B (they sum to 9).

- **Matchup outcome vs B:** W if `cats_won > cats_lost`, L if fewer, T if equal.
- **Avg Cats** (user's choice A): `sum over opponents of (cats_won + 0.5 × cats_tied) / opponents`,
  rounded to 2 decimals. Range 0–9.
- **All-play record:** counts of W, L, T matchups over all opponents (opponents = teams − 1).
- **Win %:** `(W + 0.5 × T) / (W + L + T)`, rounded to 3 decimals.
- **Week order** (user's choice): Avg Cats descending, then Win % descending, then name.
  **Week place**: 1 + number of teams with a strictly higher Avg Cats (the "min" tie method the
  rankings use; Win % breaks ties in display order only, not in place).

All teams in the week's stats take part, including a team with no real matchup (playoff bye or
eliminated team); its real-matchup column just shows nothing.

## Season totals

- **Weeks counted:** completed weeks of the current season: `start_week … current_week − 1`,
  plus `current_week` itself when its week state is not `"current"` (after the season, the last
  week turns settling, then final). The live week is never counted (call made: the season record
  shouldn't swing during the week). Playoff and consolation weeks count once reached (call made).
- **Per team:** sum of weekly W, L, T; **Win %** from those sums; **Avg Cats** is the mean of the
  team's weekly Avg Cats over the counted weeks (2 decimals); `weeks` = number of weeks counted.
- **Season order** (call made, from the user's "win–loss ranking"): Win % descending, then Avg
  Cats descending, then name. **Place**: 1 + teams with a strictly higher Win %.
- **Comparison with real results** (user's choice, after the builder check): the real results
  come from each counted week's own scoreboard (`client.week_results(week, state)`), **not** from
  Yahoo's standings, so Record, all-play and Luck always cover exactly the same weeks. (Yahoo's
  standings stop at the regular season; the season all-play totals continue through the
  playoffs.)
  - **Record:** the sum of the team's real category W–L–T (`MatchupResult.wins/losses/ties`)
    over the counted weeks in which it had a matchup. During the playoffs this differs from the
    Full Season table's Record, which is regular season only; that is accepted.
  - **Luck** (call made): over the counted weeks in which the team had a real matchup, the mean
    of `(real cats_won + 0.5 × real cats_tied) − that week's Avg Cats`. Positive = has won more
    categories than their all-play strength predicts. Signed, 2 decimals. Weeks without a
    matchup (bye, eliminated with no consolation game) are left out of Luck and Record but still
    count toward the all-play totals. `null` when the team had no matchup in any counted week.
- A team that appears in some weeks but not others (shouldn't happen in a fixed league) is
  averaged over the weeks it appears in.
- **No completed weeks yet** (week 1): return an empty `teams` list with `weeks: 0`; the UI shows
  "No completed weeks yet".

## API

### Week responses (`GET /api/rankings/week/<week>`): new field per team

```json
"all_play": {
  "avg_cats": 5.67, "wins": 9, "losses": 1, "ties": 0, "pct": 0.9, "place": 1,
  "vs": {"466.l.11070.t.4": {"wins": 6, "losses": 3, "ties": 0}}
}
```

- `vs` holds one entry per opponent, keyed by `team_key`, counting categories from this team's
  side. It feeds the head-to-head grid.
- Season responses (`/api/rankings/season`, `/api/seasons/<season>`) are unchanged: all-play is
  computed in the week route, not in `build_rankings`.
- The `teams` order of the week response does not change (still by avg rank); the client sorts
  by `all_play.place` then the stated tie-breaks for the All-Play tab. *(Builder may instead send
  the order explicitly; either is fine as long as Python defines it.)*
- Clients treat `all_play` as optional: browsers can hold final-week JSON cached for up to a day
  from before this field existed. The All-Play tab then shows "Reload to see all-play numbers"
  in place of the week tables.
- Caching is unchanged: `all_play` is derived from the same stats, so it follows the week's
  existing headers.

### New: `GET /api/allplay/season`

```json
{
  "scope": "allplay-season",
  "fetched_at": "2026-11-16T05:41:00Z",
  "stale": false,
  "refresh_throttled": false,
  "weeks": 4,
  "first_week": 1,
  "last_week": 4,
  "teams": [
    {"team_key": "466.l.11070.t.3", "name": "Team C", "place": 1,
     "wins": 31, "losses": 7, "ties": 2, "pct": 0.8, "avg_cats": 5.41, "weeks": 4,
     "record": {"wins": 22, "losses": 13, "ties": 1}, "luck": -0.21}
  ]
}
```

- Teams sorted by the season order above.
- Each week's stats come from `client.week_stats(week, current_week, refresh=...)`, so finished
  weeks hit the server's in-memory cache (final weeks kept forever; settling weeks 1 h). A cold
  instance makes one Yahoo call per counted week (about 4 today, up to about 23 at season's end).
- Each counted week's scoreboard comes from `client.week_results(week, state, refresh=...)`,
  cached the same way (final kept forever). A cold instance therefore makes about two Yahoo
  calls per counted week (about 8 today, up to about 46 at season's end). No standings call.
- `fetched_at` = the oldest `fetched_at` among the week stats and scoreboard results (the least
  fresh input). `stale` = any of them is stale. `refresh_throttled` = every refreshable input
  reported throttled.
- `?refresh=1` passes through to the week stats and scoreboard fetches (final weeks ignore it,
  as today).
- **Failure:** if any counted week's **stats** raise `YahooUnavailable` (no cached copy to fall
  back on), the whole endpoint fails with the standard 503 error body (anti-goal: no silently
  short season). If any counted week's **scoreboard** fails, return the all-play data with
  `record` and `luck` `null` for every team and `no-store` headers (same pattern as the week
  route's missing `result`), so a partial Record is never shown.
- **Headers:** `short` (60 s browser / 60 s CDN), `none` when stale, refreshing, or a scoreboard
  missing.

## Frontend

- **Tab:** `TabBar` gets `{ id: 'allplay', label: 'All-Play' }` after Star Power. `App`'s hash
  routing learns `#allplay`. Like Star Power, the tab mounts on first open and stays mounted
  (hidden) after that.
- **Week section:** reuses `App`'s existing week state (`chosenWeek`, `current`/`past`, `shown`)
  so the Rankings and All-Play tabs always show the same week, the arrows on either tab move
  both, and switching tabs never refetches. Same title ("Week N"), badge (Live / Settling /
  Final / Season over), arrows and Refresh button as the Rankings week section.
  - **All-play table** columns: place (🥇🥈🥉 for places 1–3), Team, Avg Cats, All-Play (W–L–T),
    Win % (".900" style), and the real matchup ("W 6–3–0 vs Team F"; live weeks show the
    in-progress score coloured by who leads, exactly as the Rankings Matchup/Result column does
    today; reuse that cell).
  - **Head-to-head grid** below it: rows and columns both in all-play order; each cell is the row
    team's W–L–T vs the column team, shaded with the existing win / loss / tie colours; the
    diagonal shows "—". It scrolls sideways inside its card with the team column pinned, like
    the stat table. Column headers may abbreviate team names; full name in a `title`.
- **Season section** (below a divider, as on the Rankings tab): title "Season All-Play", caption
  "Weeks F–L" (or "No completed weeks yet"). Columns: place (medals 1–3), Team, All-Play
  (W–L–T), Win %, Avg Cats, Record, Luck (signed, green when positive, red when negative,
  "—" when null). Fetched from `/api/allplay/season` when the tab is first opened, with the
  usual loading skeleton, error card with "Try again", and "Couldn't update" notice on a failed
  refresh. The tab's Refresh button also reloads the season data.
- **Header:** on the All-Play tab, the header's time and stale notice describe the week data
  (same source as on the Rankings tab).
- New types in `api.ts` mirror the API above.

## Approaches considered

- **Compute on the server, add `all_play` to the week response (chosen for the week).** Scoring
  lives in Python next to the rank logic, tested the same way, cached with the week; the tab
  reads data already loaded.
- **Compute in the browser** from the week totals: no backend change, but a second definition
  of "who wins a category" (ties, missing values, TO) that can drift from Python. Rejected.
- **Separate `/api/allplay/<week>` endpoint:** an extra request and duplicated caching and
  finality rules for data the week response already has. Rejected.
- **Season: new `/api/allplay/season` endpoint reading cached week totals (chosen).** One browser
  request; one scoring definition; finished weeks fetched from Yahoo once per server instance.
- **Season: browser fetches every week and sums:** 4–23 requests per phone plus the scoring in
  TypeScript. Rejected.
- **Season: database plus a nightly job:** adds storage and a scheduled job to a $0 site to save
  a handful of cached calls. Rejected.

## Calls made without asking

- The week arrows are shared between the Rankings and All-Play tabs.
- Win % is the secondary sort for the week table; Avg Cats the secondary sort for the season.
- Season order is by Win % (from "overall win–loss ranking"); the week order stays Avg Cats.
- Only completed weeks count toward the season; the live week does not.
- Playoff and consolation weeks count toward the season once played.
- The season table shows a Record plus a Luck column (real cats won − Avg Cats, averaged over
  weeks with a real matchup). Record and Luck are built from each week's scoreboard (user's
  choice); the Luck formula and leaving bye weeks out of it are my calls.
- A failed week's stats fail the season endpoint rather than returning a shorter season; a
  failed week's scoreboard only blanks Record and Luck.
- Current season only.

## Left to the builder

- Function and module names (e.g. an `all_play.py` beside `rankings.py`), and whether the week
  order is sent explicitly or derived client-side from `place` plus the stated tie-breaks.
- Whether the season endpoint fetches weeks sequentially or in parallel (a cold instance at
  season's end makes about 46 calls; Vercel's limit is 300 s).
- Exact column header abbreviations and cell styling, within the existing design language.
- Tests: Python unit tests for the scoring (ties, `None`s, TO direction, place ties, Luck incl.
  bye weeks, week selection incl. after-season and week 1), API tests for both routes (headers,
  503 on a failed week's stats, blank Record/Luck on a failed scoreboard), and Vitest tests for
  the tab, grid and season table. The real week-3 fixtures (`week_stats.json`,
  `scoreboard.json`) make a good cross-check: the scoring reproduces Yahoo's real category
  W–L–T for every actual pairing.

## Docs to update with the code

`docs/api.md` (week field, new endpoint), `docs/architecture.md` (new module, tab, endpoint),
`docs/decisions.md` (the calls above), and the README feature list if it has one.
