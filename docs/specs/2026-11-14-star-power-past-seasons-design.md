# Star Power for past seasons

**Date:** 2026-11-14 · **Status:** implemented (user said "just dive in"; no separate plan) ·
**Size:** small change (short design)

## Intent

The Star Power tab gets the same ‹ › season arrows as Full Season, so a finished season
(today only 2025-26) shows how many of that season's top 10, 25 and 50 players each team had.

## Goals and non-goals

- **Goal:** the same table as today's Star Power, for any finished season the account can read.
- **Ownership = end-of-season rosters** (the user's choice). A player traded mid-season counts
  only for the team that finished with him.
- **Non-goals:** who drafted a player, or who had him longest (both possible from past-week
  rosters and draft results, but many more Yahoo calls). Other ranking windows.

## Data (checked live 2026-11-14)

The current endpoint's request works unchanged on a past league
(`league/466.l.11070/players;sort=AR;sort_type=season;start=N;count=25/ownership`). It returns
the final full-season ranks, and `ownership` shows the end-of-season owner.

## Approaches considered

- **End-of-season rosters from the existing request (chosen).** No extra calls, and a finished
  season can be cached forever.
- **Who drafted the player** (`draftresults`): one call, but ignores trades and pickups.
- **Who had the player longest** (past-week rosters): about 10 teams × 23 weeks of calls.

## Design

- **API:** `GET /api/stars/<season>`, the same body as `/api/stars` plus `season` and
  `league_key`. It uses the same season lookup as `/api/seasons/<season>` (shared
  `_finished_season`), so it gives 404 for the in-progress season, unknown seasons and bad input,
  and 503 when an outage cut the season list short.
- **Client:** `season_top_players(league_key, finished)` and `season_teams(league_key, finished)`.
  A finished season is cached forever, with final CDN headers once both are final.
  `season_teams` uses the same cache entry as `final_season`'s stats.
- **Frontend:** `StarPowerSection` fetches `/api/seasons` and shows `ArrowNav` when there is more
  than one season. It uses the same rule as Full Season for when to show the final view.
  - **Badge:** "Final · top 50" (or "Past season · top 50").
  - **Caption:** "Full-season ranks · rosters at season end" instead of "As of".
  - **Refresh:** no button, because the data is final.

## Calls made (not discussed)

- **Season choice:** Star Power's chosen season is independent of Full Season's.
- **Refresh button:** hidden on past seasons.
- **Off-season:** the current season switches to the final view once Yahoo marks it finished,
  the same as Full Season does.
