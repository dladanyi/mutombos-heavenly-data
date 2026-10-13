"""Parsing tests against fixtures in Yahoo's JSON shape.

Shapes (see fixtures/README.md; currently synthetic):
- league:      fantasy_content.league[0] = metadata dict (current_week int, start/end_week strings)
- teams/stats: fantasy_content.league[1].teams = {"0": {"team": [metadata_list, {"team_stats": ...}]}, ..., "count": N}
               metadata_list mixes single-key dicts and empty lists
- game_weeks:  fantasy_content.game[1].game_weeks = {"0": {"game_week": {week, start, end}}, ..., "count": N}
"""
import copy
import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.errors import YahooFormatError
from app.parsing import parse_game_weeks, parse_league, parse_team_stats

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_season_fixture_parses_one_row_per_team():
    teams = parse_team_stats(load("season_stats.json"))
    league = load("league.json")["fantasy_content"]["league"][0]
    assert len(teams) == league["num_teams"]
    assert all(t.name for t in teams)
    assert all("5" in t.values for t in teams)
    assert teams[0].team_key.endswith(".t.1")


def test_week_fixture_has_fg_detail():
    teams = parse_team_stats(load("week_stats.json"))
    assert all(re.fullmatch(r"\d+/\d+", t.values["9004003"]) for t in teams)


def test_team_metadata_order_does_not_matter():
    payload = load("season_stats.json")
    reordered = copy.deepcopy(payload)
    for key, value in reordered["fantasy_content"]["league"][1]["teams"].items():
        if key != "count":
            value["team"][0].reverse()
            value["team"].reverse()
    assert parse_team_stats(reordered) == parse_team_stats(payload)


def test_missing_teams_raises_format_error():
    with pytest.raises(YahooFormatError):
        parse_team_stats({"fantasy_content": {"league": [{}]}})


def test_team_without_name_raises_format_error():
    payload = load("week_stats.json")
    team = payload["fantasy_content"]["league"][1]["teams"]["0"]["team"]
    team[0] = [item for item in team[0] if not (isinstance(item, dict) and "name" in item)]
    with pytest.raises(YahooFormatError):
        parse_team_stats(payload)


def test_not_a_dict_raises_format_error():
    with pytest.raises(YahooFormatError):
        parse_team_stats([])


def test_parse_league_fixture():
    league = parse_league(load("league.json"))
    assert league.name == "Mutombo's Heavenly Block Party"
    assert all(isinstance(v, int) for v in (league.current_week, league.start_week, league.end_week))
    assert league.start_week <= league.current_week <= league.end_week


def test_parse_league_missing_field_raises():
    payload = load("league.json")
    del payload["fantasy_content"]["league"][0]["current_week"]
    with pytest.raises(YahooFormatError):
        parse_league(payload)


def test_parse_game_weeks_fixture():
    weeks = parse_game_weeks(load("game_weeks.json"))
    league = parse_league(load("league.json"))
    assert set(range(league.start_week, league.end_week + 1)) <= set(weeks)
    for number, week in weeks.items():
        assert week.week == number
        assert isinstance(week.start, date) and isinstance(week.end, date)
        assert week.start <= week.end


def test_parse_game_weeks_bad_date_raises():
    payload = load("game_weeks.json")
    payload["fantasy_content"]["game"][1]["game_weeks"]["0"]["game_week"]["end"] = "soon"
    with pytest.raises(YahooFormatError):
        parse_game_weeks(payload)
