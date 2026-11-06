import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.parsing import GameWeek

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_league_weeks.py"
spec = importlib.util.spec_from_file_location("check_league_weeks", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def calendar(*lengths, start=date(2026, 10, 20)):
    """Consecutive game weeks with the given lengths in days, numbered from 1."""
    weeks = {}
    for number, days in enumerate(lengths, start=1):
        weeks[number] = GameWeek(number, start, start + timedelta(days=days - 1))
        start += timedelta(days=days)
    return weeks


def bounds_from(cal, weeks):
    return {n: {(cal[n].start, cal[n].end)} for n in weeks}


def test_matching_league_has_no_problems():
    cal = calendar(6, 7, 14, 7, 7)
    assert check.compare_weeks(bounds_from(cal, [1, 2, 3, 4, 5]), cal, 1, 5, cal[5].end) == []


def test_unscored_weeks_checked_through_league_end_date():
    cal = calendar(6, 7, 7, 7, 7)  # weeks 4-5 are playoffs with no matchups yet
    league = {**bounds_from(cal, [1, 2, 3]), 4: set(), 5: set()}
    assert check.compare_weeks(league, cal, 1, 5, cal[5].end) == []


def test_league_week_with_different_bounds_is_reported():
    cal = calendar(6, 7, 14)
    league = bounds_from(cal, [1, 2])
    league[3] = {(cal[3].start, cal[3].start + timedelta(days=6))}  # league splits the long week
    problems = check.compare_weeks(league, cal, 1, 3, cal[3].end)
    assert len(problems) == 1 and "week 3" in problems[0]


def test_matchups_disagreeing_within_a_week_is_reported():
    cal = calendar(7, 7)
    league = bounds_from(cal, [1, 2])
    league[2].add((cal[2].start, cal[2].end + timedelta(days=1)))
    assert any("week 2" in p for p in check.compare_weeks(league, cal, 1, 2, cal[2].end))


def test_calendar_missing_a_league_week_is_reported():
    cal = calendar(7, 7)
    league = {1: {(cal[1].start, cal[1].end)}, 2: {(cal[2].start, cal[2].end)}, 3: set()}
    assert any("week 3" in p for p in check.compare_weeks(league, cal, 1, 3, cal[2].end))


def test_season_end_mismatch_is_reported():
    cal = calendar(7, 7, 7)
    league = {**bounds_from(cal, [1]), 2: set(), 3: set()}
    problems = check.compare_weeks(league, cal, 1, 3, cal[3].end + timedelta(days=7))
    assert any("end_date" in p for p in problems)


def test_gap_in_calendar_is_reported():
    cal = calendar(7, 7, 7)
    cal[3] = GameWeek(3, cal[3].start + timedelta(days=1), cal[3].end)
    league = {**bounds_from(cal, [1, 2]), 3: set()}
    assert any("gap" in p for p in check.compare_weeks(league, cal, 1, 3, cal[3].end))


def scoreboard(matchups):
    return {"0": {"matchups": matchups}} if matchups is not None else {"0": {}}


def test_matchup_bounds_reads_each_matchup():
    m = {"matchup": {"week": "3", "week_start": "2026-11-02", "week_end": "2026-11-08"}}
    assert check.matchup_bounds(scoreboard({"0": m, "1": m, "count": 2})) == {(date(2026, 11, 2), date(2026, 11, 8))}


@pytest.mark.parametrize("matchups", [None, [], {"count": 0}, {"count": 0, "extra": {"x": 1}}])
def test_matchup_bounds_empty_shapes_mean_no_matchups(matchups):
    assert check.matchup_bounds(scoreboard(matchups)) == set()


def test_matchup_bounds_handles_empty_scoreboard():
    assert check.matchup_bounds({}) == set()
    assert check.matchup_bounds([]) == set()


def test_unscored_weeks_are_listed_as_provisional():
    assert check.unscored_weeks({1: {(date(2026, 10, 20), date(2026, 10, 25))}, 2: set(), 3: set()}) == [2, 3]
