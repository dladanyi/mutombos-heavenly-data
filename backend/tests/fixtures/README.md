# Test fixtures

Real Yahoo Fantasy API responses for league 46425 (2026-27 season), captured 2026-11-05 by
`backend/scripts/capture_fixtures.py`, when the current week was 3. `week_stats.json` is week 2.

| File | Yahoo endpoint |
|---|---|
| `league.json` | `league/nba.l.46425` |
| `season_stats.json` | `league/nba.l.46425/teams/stats` |
| `week_stats.json` | `league/nba.l.46425/teams/stats;type=week;week=2` |
| `game_weeks.json` | `game/nba/game_weeks` |

**The repo is public**, so the script anonymises the responses before saving them. It drops
`managers` (nicknames, GUIDs, emails), team logos, page URLs and the league chat id, and
renames each team to `Team <team_id>`. The app reads none of the dropped fields. Check the diff
for personal data before committing a new capture anyway.

To re-capture (this overwrites all four files):

```sh
set -a; source .env; set +a
.venv/bin/python backend/scripts/capture_fixtures.py
cd backend && ../.venv/bin/pytest
```

Tests that depend on the calendar (`test_yahoo_client.py`) are written against these dates
(week 3 = 2026-11-02..2026-11-08) and the league's 10 teams. Update them after a re-capture.
