"""Check that the league's own week bounds match Yahoo's NBA game calendar.

The app decides when a week is final (and gets a 1-year CDN cache) from `game/nba/game_weeks`,
looking up league week N as game week N. This holds only if the league numbers its weeks like
the game calendar. Re-run it each season (spec risk 3). It prints dates and week numbers only,
never team or manager data.

Run from the repo root:
    set -a; source .env; set +a
    .venv/bin/python backend/scripts/check_league_weeks.py

Exit codes: 0 = weeks match, 1 = mismatch found, 2 = couldn't check (Yahoo error, bad token).
Weeks with no matchups yet (playoffs before the bracket is set) can only be checked as a span,
so a 0 is PROVISIONAL for them: re-run once the bracket is set.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.parsing import GameWeek  # noqa: E402

Bounds = set[tuple[date, date]]


def compare_weeks(league: dict[int, Bounds], calendar: dict[int, GameWeek], start_week: int,
                  end_week: int, end_date: date) -> list[str]:
    """Return the problems found, or [] if the calendar is safe to use for this league.

    `league` maps each league week to the (week_start, week_end) pairs its scoreboard matchups
    report. The set is empty for weeks with no matchups yet (playoffs before the bracket is
    set). Those can't be compared directly, so the calendar must instead run without gaps
    through end_week and end on the league's end_date."""
    problems = []
    for week in range(start_week, end_week + 1):
        game_week = calendar.get(week)
        if game_week is None:
            problems.append(f"week {week}: missing from the game calendar")
            continue
        bounds = league.get(week, set())
        if len(bounds) > 1:
            problems.append(f"week {week}: matchups disagree on its bounds: {sorted(bounds)}")
        elif bounds and bounds != {(game_week.start, game_week.end)}:
            (start, end), = bounds
            problems.append(f"week {week}: league {start}..{end} but game calendar "
                            f"{game_week.start}..{game_week.end}")
        previous = calendar.get(week - 1)
        if week > start_week and previous and game_week.start != previous.end + timedelta(days=1):
            problems.append(f"week {week}: gap or overlap after week {week - 1} in the game calendar")
    last = calendar.get(end_week)
    if last is not None and last.end != end_date:
        problems.append(f"week {end_week} ends {last.end} but the league's end_date is {end_date}")
    return problems


def matchup_bounds(scoreboard) -> Bounds:
    """The (week_start, week_end) pairs of a scoreboard's matchups. A missing or empty
    `matchups` collection (Yahoo returns [] or leaves it out) means no matchups yet."""
    holder = scoreboard.get("0") if isinstance(scoreboard, dict) else None
    matchups = holder.get("matchups") if isinstance(holder, dict) else None
    if not isinstance(matchups, dict):
        return set()
    return {(date.fromisoformat(m["matchup"]["week_start"]), date.fromisoformat(m["matchup"]["week_end"]))
            for key, m in matchups.items() if key.isdigit()}


def unscored_weeks(league: dict[int, Bounds]) -> list[int]:
    """Weeks with no matchups, whose own bounds the check couldn't compare."""
    return [week for week, bounds in sorted(league.items()) if not bounds]


def main() -> int:
    try:
        return _run()
    except Exception as exc:  # noqa: BLE001 - report any failure as "couldn't check", not a mismatch
        print(f"COULD NOT CHECK: {type(exc).__name__}: {exc}")
        return 2


def _run() -> int:
    from app.config import load_settings
    from app.parsing import parse_game_weeks
    from app.yahoo_http import YahooHttp

    settings = load_settings()
    http = YahooHttp(settings.consumer_key, settings.consumer_secret, settings.refresh_token)
    league_path = f"league/nba.l.{settings.league_id}"
    meta = http.get_json(league_path)["fantasy_content"]["league"][0]
    start_week, end_week = int(meta["start_week"]), int(meta["end_week"])
    end_date = date.fromisoformat(meta["end_date"])
    calendar = parse_game_weeks(http.get_json("game/nba/game_weeks"))

    league: dict[int, Bounds] = {}
    for week in range(start_week, end_week + 1):
        parts = http.get_json(f"{league_path}/scoreboard;week={week}")["fantasy_content"]["league"]
        scoreboard = next((p["scoreboard"] for p in parts if isinstance(p, dict) and "scoreboard" in p), None)
        league[week] = matchup_bounds(scoreboard)

    print(f"league weeks {start_week}..{end_week}, end_date {end_date}")
    for week in range(start_week, end_week + 1):
        game_week = calendar.get(week)
        bounds = ", ".join(f"{s}..{e}" for s, e in sorted(league[week])) or "(no matchups yet)"
        print(f"{week:>3}  league {bounds:<24}  game {game_week.start}..{game_week.end}" if game_week
              else f"{week:>3}  league {bounds:<24}  game -")
    problems = compare_weeks(league, calendar, start_week, end_week, end_date)
    for problem in problems:
        print("MISMATCH:", problem)
    if problems:
        print("Use the league scoreboard's week_start/week_end for finality instead (spec risk 3).")
        return 1
    pending = unscored_weeks(league)
    if pending:
        print(f"PROVISIONAL: weeks {pending[0]}-{pending[-1]} have no matchups yet, so only their "
              "combined span was checked. Re-run once the bracket is set.")
    else:
        print("OK: the game calendar matches the league's weeks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
