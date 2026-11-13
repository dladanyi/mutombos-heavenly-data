"""Parsing tests against fixtures in Yahoo's JSON shape.

Shapes (see fixtures/README.md; real responses, anonymised):
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
from app.parsing import (GameWeek, MatchupResult, parse_game_weeks, parse_league, parse_scoreboard,
                         parse_team_stats)

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
    # Pinned from the real 2026-27 calendar: finality and CDN caching depend on these dates, and
    # test_yahoo_client derives its boundaries through this parser. Update after a re-capture.
    assert weeks[1] == GameWeek(1, date(2026, 10, 20), date(2026, 10, 25))
    assert weeks[3] == GameWeek(3, date(2026, 11, 2), date(2026, 11, 8))


def test_parse_game_weeks_bad_date_raises():
    payload = load("game_weeks.json")
    payload["fantasy_content"]["game"][1]["game_weeks"]["0"]["game_week"]["end"] = "soon"
    with pytest.raises(YahooFormatError):
        parse_game_weeks(payload)


# scoreboard: fantasy_content.league[1].scoreboard = {"week": N, "0": {"matchups": {"0": {"matchup": {
#   status, is_tied, winner_team_key, stat_winners: [{"stat_winner": {stat_id, winner_team_key | is_tied}}],
#   "0": {"teams": {"0": {"team": [metadata_list, ...]}, "1": ..., "count": 2}}}}, ..., "count": N}}}

def matchup_body(*matchups):
    entries = {str(i): {"matchup": m} for i, m in enumerate(matchups)}
    return {"fantasy_content": {"league": [{"league_key": "nba.l.1"},
                                           {"scoreboard": {"week": 3, "0": {"matchups": {**entries, "count": len(matchups)}}}}]}}


def matchup(a="k.1", b="k.2", winners=("k.1", "k.1", "k.2", None), status="postevent", tied=0, winner="k.1"):
    team = lambda key: {"team": [[{"team_key": key}, {"team_id": key[-1]}, {"name": f"Team {key}"}, []]]}
    m = {"status": status, "is_tied": tied,
         "stat_winners": [{"stat_winner": {"stat_id": str(i), **({"winner_team_key": w} if w else {"is_tied": 1})}}
                          for i, w in enumerate(winners)],
         "0": {"teams": {"0": team(a), "1": team(b), "count": 2}}}
    if winner:
        m["winner_team_key"] = winner
    return m


def test_scoreboard_fixture_gives_every_team_a_consistent_result():
    raw = load("scoreboard.json")
    results = parse_scoreboard(raw)
    league = load("league.json")["fantasy_content"]["league"][0]
    matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]
    assert len(results) == 2 * int(matchups["count"]) == league["num_teams"]
    for key, r in results.items():
        opp = results[r.opponent_key]
        assert opp.opponent_key == key and r.opponent_name == f"Team {r.opponent_key.rsplit('.', 1)[1]}"
        assert (r.wins, r.losses, r.ties) == (opp.losses, opp.wins, opp.ties)
        assert r.wins + r.losses + r.ties == 9
        assert {r.outcome, opp.outcome} == {"W", "L"} and (r.outcome == "W") == (r.wins > r.losses)


def test_scoreboard_counts_wins_losses_and_ties():
    results = parse_scoreboard(matchup_body(matchup()))
    assert results["k.1"] == MatchupResult("W", 2, 1, 1, "k.2", "Team k.2")
    assert results["k.2"] == MatchupResult("L", 1, 2, 1, "k.1", "Team k.1")


def test_scoreboard_tied_matchup():
    results = parse_scoreboard(matchup_body(matchup(winners=("k.1", "k.2"), tied=1, winner=None)))
    assert results["k.1"].outcome == results["k.2"].outcome == "T"


def test_scoreboard_unfinished_matchup_has_no_outcome():
    results = parse_scoreboard(matchup_body(matchup(status="midevent")))
    assert results["k.1"].outcome is None and results["k.1"].wins == 2


@pytest.mark.parametrize("matchups", [[], None, {"count": 0}])
def test_scoreboard_without_matchups_is_empty(matchups):
    body = matchup_body()
    holder = body["fantasy_content"]["league"][1]["scoreboard"]["0"]
    if matchups is None:
        del holder["matchups"]
    else:
        holder["matchups"] = matchups
    assert parse_scoreboard(body) == {}


@pytest.mark.parametrize("breakage", ["no_teams", "one_team", "bad_stat_winner"])
def test_scoreboard_malformed_raises(breakage):
    m = matchup()
    if breakage == "no_teams":
        del m["0"]
    elif breakage == "one_team":
        del m["0"]["teams"]["1"]
    else:
        m["stat_winners"] = [{"oops": 1}]
    with pytest.raises(YahooFormatError):
        parse_scoreboard(matchup_body(m))


def test_scoreboard_finished_without_winner_has_no_outcome():
    results = parse_scoreboard(matchup_body(matchup(winner=None)))
    assert results["k.1"].outcome is None and results["k.2"].outcome is None
