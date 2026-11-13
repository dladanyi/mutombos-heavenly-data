# Test fixtures

Real Yahoo Fantasy API responses for league 46425 (2026-27 season), captured 2026-11-13 by
`backend/scripts/capture_fixtures.py`, when the current week was 4. `week_stats.json` and
`scoreboard.json` are week 3.

| File | Yahoo endpoint |
|---|---|
| `league.json` | `league/nba.l.46425` |
| `season_stats.json` | `league/nba.l.46425/teams/stats` |
| `week_stats.json` | `league/nba.l.46425/teams/stats;type=week;week=3` |
| `scoreboard.json` | `league/nba.l.46425/scoreboard;week=3` |
| `game_weeks.json` | `game/nba/game_weeks` |

**The repo is public**, so the script anonymises the responses before saving them, using
**allowlists** (`TEAM_META_KEEP`, `TEAM_PARTS_KEEP`, `LEAGUE_META_KEEP`, `MATCHUP_KEEP`,
`STAT_WINNER_KEEP` in the script):

- Each team keeps only `team_key`, `team_id`, `name` (renamed to `Team <team_id>`; the
  parser requires it) and its `team_stats`. Everything else is dropped: managers, logos, URLs,
  `is_owned_by_current_login`, draft position, waiver priority, and any field Yahoo adds later.
  The rename is cosmetic, because the dashboard shows real team names and the same stats. What
  matters is keeping out managers and ownership, which aren't public.
  Yahoo's empty-list placeholders in the metadata list are kept, because the parser has to
  handle them.
- League metadata keeps its name, key, season, team count, week range and dates.
- Scoreboard matchups keep only their result fields (`MATCHUP_KEEP`: week, dates, status,
  playoff flags, `is_tied`, `winner_team_key`, `stat_winners`, each stat winner reduced to
  `STAT_WINNER_KEEP`). Their two teams go through the same team allowlists as above.
- `game_weeks.json` is saved as returned. It's Yahoo's public NBA calendar.
- The wrappers around these are rebuilt with only their known keys too: the `teams` part,
  each team entry, and the top-level `fantasy_content` envelope.

The script raises an error and writes nothing if a response has a shape the allowlists don't
cover: a team without a `team_id`, a league part other than the metadata, `teams` and
`scoreboard` (for example standings), a scoreboard with keys besides `week` and its
matchups, a matchup whose teams holder isn't exactly `{"teams": ...}`, or any response that is
neither a league nor the `game_weeks` calendar (for example a `users` payload). Add an allowlist for it first. Files
are written to temp names and renamed only once all five writes succeed.

`test_parsing.py` pins two real calendar dates (weeks 1 and 3) because the finality tests
take their boundaries through the parser. Update those after a re-capture for a new season. If `parsing.py` starts reading a new field, add it to the allowlist and re-capture.
Check the diff for personal data before committing a new capture anyway.

To re-capture (this overwrites all five files):

```sh
set -a; source .env; set +a
.venv/bin/python backend/scripts/capture_fixtures.py
cd backend && ../.venv/bin/pytest
```

The calendar tests (`test_yahoo_client.py`) take the league id, team count, current week and
week 3's end date from these files, so they follow a re-capture.
