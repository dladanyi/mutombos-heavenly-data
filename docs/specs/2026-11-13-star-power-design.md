# Star Power: teams ranked by their top-10/25/50 players

**Date:** 2026-11-13 · **Status:** approved 2026-11-13; implemented (plan: `docs/plans/2026-11-13-star-power.md`) · **Size:** small project (short design)

## Intent

A second screen that shows which teams have the most stars right now: how many of each team's
players are in the season-to-date top 10, top 25 and top 50, with the players listed by rank.

## Goals

- A **Star Power** tab next to the existing rankings.
- Teams ordered by top-10 count, then top-25, then top-50 (the user's choice). Ties share a
  place.
- Each team's top-50 players listed with rank, name, NBA team and position.

## Non-goals

- Other ranking windows (last month, last week, preseason) and anything past the top 50.
- Player stats, injury status, trends.

## Data (checked live 2026-11-13)

- **Rankings:** `league/<key>/players;sort=AR;sort_type=season;start=N;count=25/ownership`.
  This is Yahoo's season-to-date "actual rank" in this league's categories. The response
  carries no rank number, so a player's rank is his position in the sorted list
  (`start + index + 1`). Yahoo returns at most 25 players per call, so the top 50 takes two
  calls (`start=0` and `start=25`).
- **Ownership:** each player's `ownership` has `ownership_type` (`team`, `freeagents` or
  `waivers`) and, for `team`, `owner_team_key` and `owner_team_name`.
- **Player fields used:** `player_key`, `name.full`, `editorial_team_abbr`,
  `display_position`.

## Approaches considered

- **A. Tabs on the same page, with the tab kept in the URL hash as `#stars` (chosen by the
  user).** No new dependency and no hosting change. It can be bookmarked, and Back works.
- **B. A separate `/stars` URL with a router library.** It adds a dependency and a Vercel
  rewrite for deep links.
- **C. A third section on the current page.** That isn't a separate screen, and the page is
  already long.

## Design

### Display

```
[ Rankings ]  [ Star Power ]

STAR POWER   Season to date · top 50                    [Refresh]
 #  Team                   Top 10  Top 25  Top 50
 1  This Land is Garland      2       4       7
      1 Victor Wembanyama SAS C · 8 … · 14 … · 31 …
 …
 Not on a team: 37 Player X (FA) · 48 Player Y (W)
```

- **Counts:** cumulative ("top 25" includes the top-10 players).
- **Team order:** most top-10 players, then top 25, then top 50. Ties share a place. Equal
  teams are listed by name. The # column gets gold, silver and bronze for places 1–3, the same
  as the other tables.
- **Player list:** each team row has a player line underneath, in rank order. Each player
  shows rank, name, NBA team and position. Players in the top 10 are marked ★, so the stars
  stand out. A team with no top-50 players shows "No top-50 players".
- **Unowned players:** top-50 players on no team (free agents or waivers) are listed in one
  "Not on a team" line under the table, so the counts make sense.

### API

`GET /api/stars`:

```json
{
  "fetched_at": "...", "stale": false, "refresh_throttled": false,
  "levels": [10, 25, 50],
  "teams": [
    {"team_key": "478.l.46425.t.5", "name": "...", "place": 1,
     "counts": {"10": 2, "25": 4, "50": 7},
     "players": [{"rank": 1, "player_key": "...", "name": "Victor Wembanyama",
                  "nba_team": "SAS", "position": "C"}]}
  ],
  "unowned": [{"rank": 37, "player_key": "...", "name": "...", "nba_team": "...",
               "position": "...", "status": "freeagents"}]
}
```

- **Which teams:** every team in the league is listed, including teams with 0 top-50 players.
  The team list comes from the season stats the app already fetches (cached), so a team with
  no stars still shows up.
- **Caching:** the server cache keeps the rankings for **1 hour** (Yahoo updates season
  ranks about daily), and both pages are cached together. Headers are browser
  `public, max-age=300` and CDN `max-age=3600`. `?refresh=1` skips the cache, throttled to
  once per 30 s like the other endpoints. Stale responses or refreshes are sent `no-store`.
  (My call: 1 hour rather than the 5 minutes the live data uses.)
- **Errors:** if Yahoo fails with nothing cached, the endpoint returns 503, as the others do.

### Backend

- **Parsing:** `parsing.parse_ranked_players(payload, start) -> list[RankedPlayer]`, with
  `rank`, `player_key`, `name`, `nba_team`, `position`, `owner_team_key | None` and
  `ownership_type`.
- **Yahoo client:** `YahooClient.top_players(refresh) -> (list[RankedPlayer], CacheResult)`
  fetches both pages under one cache key with a 1-hour TTL.
- **Grouping:** a small `stars.py` with `build_star_power(players, teams) -> dict`. It does
  the counts, the order, `place` and the unowned list. It's plain Python like
  `rankings.py`, so it's easy to unit test.
- **Fixtures:** the capture script gains a players allowlist that keeps only the fields above
  plus `ownership` reduced to its type and owner team key. No managers and no URLs, because
  the repo is public.

### Frontend

- **Tabs:** under the header, a tab bar with "Rankings" and "Star Power". Real buttons, with
  `aria-selected`. The URL hash is `#stars`. Rankings is the default, and Back works.
- **Data:** Star Power is fetched only when its tab is opened.
- **New components:** `StarPowerSection` (with a Refresh button) and `StarPowerTable`.
- **Phone width (390 px):** the table scrolls inside its card with Team pinned, as the other
  tables do, and the player line wraps.

## Calls made (not discussed)

- **Cache:** 1-hour server/CDN cache for Star Power.
- **Display:** ★ marks top-10 players; places 1–3 get medals; teams are listed even with 0
  top-50 players.
- **Navigation:** the tab bar sits under the header. The header's "Last updated" time and
  outage notice describe the rankings, so they're hidden on the Star Power tab, which shows its
  own "As of" time and stale notice (changed after review). A tab stays mounted once opened, so
  switching back keeps its data.
