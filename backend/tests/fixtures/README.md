# Test fixtures

Real Yahoo Fantasy API responses for league 46425 (2026-27 season), captured 2026-11-05 by
`backend/scripts/capture_fixtures.py`, when the current week was 3. `week_stats.json` is week 2.

| File | Yahoo endpoint |
|---|---|
| `league.json` | `league/nba.l.46425` |
| `season_stats.json` | `league/nba.l.46425/teams/stats` |
| `week_stats.json` | `league/nba.l.46425/teams/stats;type=week;week=2` |
| `game_weeks.json` | `game/nba/game_weeks` |

**The repo is public**, so the script anonymises the responses before saving them, using
**allowlists** (`TEAM_META_KEEP`, `TEAM_PARTS_KEEP`, `LEAGUE_META_KEEP` in the script):

- Each team keeps only `team_key`, `team_id` and its `team_stats`, and is renamed to
  `Team <team_id>`. Everything else is dropped: managers, logos, URLs,
  `is_owned_by_current_login`, draft position, waiver priority, and any field Yahoo adds later.
  The rename is cosmetic, because the dashboard shows real team names and the same stats. What
  matters is keeping out managers and ownership, which aren't public.
  Yahoo's empty-list placeholders in the metadata list are kept, because the parser has to
  handle them.
- League metadata keeps its name, key, season, team count, week range and dates.
- `game_weeks.json` is saved as returned. It's Yahoo's public NBA calendar.

The script raises an error and writes nothing if a response has a shape the allowlists don't
cover: a team without a `team_id`, or a league part other than the metadata and `teams` (for
example standings or a scoreboard). Add an allowlist for that part first. Files are written
to temp names and renamed only once all four succeed. If `parsing.py` starts reading a new field, add it to the allowlist and re-capture.
Check the diff for personal data before committing a new capture anyway.

To re-capture (this overwrites all four files):

```sh
set -a; source .env; set +a
.venv/bin/python backend/scripts/capture_fixtures.py
cd backend && ../.venv/bin/pytest
```

The calendar tests (`test_yahoo_client.py`) take the league id, team count, current week and
week 3's end date from these files, so they follow a re-capture.
