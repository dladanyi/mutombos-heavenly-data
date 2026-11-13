# Weekly head-to-head results on the last-week table

**Date:** 2026-11-13 · **Status:** implemented

## Intent

The last-week table ranks teams by their stats, but it didn't say who actually won their
head-to-head matchup. Show each team's result next to its name, so the stat ranks and the real
outcome can be read together (e.g. the top three by average rank all lost in week 3).

## What it shows

A **Result** column right after **Team**, in the last-week table only: `W 5–3–1 vs Team D`.
The score is categories won–lost, with –tied only when there were ties. W is green, L red,
T gold; the opponent is muted. A dash means no matchup (playoff bye) or results unavailable.
A matchup Yahoo hasn't marked finished shows the score without W/L/T.

## Approaches considered

- **A. A W/L/T marker only.** Smallest, but drops the opponent and how close it was.
- **B. Result + score + opponent (chosen by the user).** A little more than A, and it's the
  first piece of sub-project 3.
- **C. Full matchup cards with per-category winners.** That is sub-project 3 itself.

## Design

- **Data:** Yahoo's `league/<key>/scoreboard;week=N`. Each matchup has `status` (`postevent`
  when finished), `is_tied`, `winner_team_key`, and `stat_winners` (one per category, a
  winner or `is_tied`). Category counts come from `stat_winners`, not `team_points`. A matchup without `stat_winners` counts
  as 0–0 rather than dropping every team's result.
- **Backend:** `parsing.parse_scoreboard` → `{team_key: MatchupResult}`;
  `YahooClient.week_results` caches it with the same current/settling/final rules as the
  week's stats. The week route adds `result` to each row only when the week isn't current, so
  the live week costs no extra Yahoo call.
- **Failure:** if the scoreboard fails (Yahoo down or an unexpected shape), the rankings are
  still returned with `result: null` and `no-store`, so the gap is never cached. A final week
  gets the long CDN cache only when both stats and scoreboard were fetched as final.
- **Fixtures:** `capture_fixtures.py` gained a scoreboard allowlist (the repo is public); the
  fixtures were re-captured on 2026-11-13.

## Calls made without asking

- Last-week table only (the request), although the API returns results for any finished week.
- Opponent name comes from the scoreboard response.
- Results during the 3-day settling window are shown as Yahoo reports them; a stat correction
  could in theory flip a close result, and the 1-hour settling cache picks that up.
