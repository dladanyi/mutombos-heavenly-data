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
                         parse_ranked_players, parse_standings, parse_team_stats)

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


@pytest.mark.parametrize("breakage", ["no_teams", "one_team", "bad_stat_winner", "null_stat_winners",
                                      "stat_winner_list", "stat_winner_string"])
def test_scoreboard_malformed_raises(breakage):
    m = matchup()
    if breakage == "no_teams":
        del m["0"]
    elif breakage == "one_team":
        del m["0"]["teams"]["1"]
    elif breakage == "bad_stat_winner":
        m["stat_winners"] = [{"oops": 1}]
    elif breakage == "null_stat_winners":
        m["stat_winners"] = None
    elif breakage == "stat_winner_list":
        m["stat_winners"] = [{"stat_winner": []}]
    else:
        m["stat_winners"] = ["x"]
    with pytest.raises(YahooFormatError):
        parse_scoreboard(matchup_body(m))


def test_scoreboard_finished_without_winner_has_no_outcome():
    results = parse_scoreboard(matchup_body(matchup(winner=None)))
    assert results["k.1"].outcome is None and results["k.2"].outcome is None


def test_scoreboard_matchup_without_stat_winners_counts_zero():
    m = matchup(status="midevent", winner=None)
    del m["stat_winners"]
    results = parse_scoreboard(matchup_body(m, matchup(a="k.3", b="k.4", winners=("k.3",), winner="k.3")))
    assert (results["k.1"].wins, results["k.1"].losses, results["k.1"].ties) == (0, 0, 0)
    assert results["k.3"].outcome == "W"



# league metadata: season (string), renew ("<game_key>_<league_id>" or ""), is_finished (1 when done)
# standings:  fantasy_content.league[1].standings = [{"teams": {"0": {"team": [metadata_list,
#             {"team_standings": {rank, playoff_seed, outcome_totals: {wins, losses, ties, percentage}}}]}, ...}}]

def test_parse_league_season_fields():
    league = parse_league(load("prev_league.json"))
    assert (league.season, league.league_key, league.is_finished, league.previous_league_key) == (
        2025, "466.l.11070", True, "454.l.37383")


@pytest.mark.parametrize("renew", ["", None])
def test_parse_league_renew_empty_or_missing(renew):
    payload = load("prev_league.json")
    meta = payload["fantasy_content"]["league"][0]
    meta.pop("is_finished", None)
    if renew is None:
        meta.pop("renew", None)
    else:
        meta["renew"] = renew
    league = parse_league(payload)
    assert league.previous_league_key is None and league.is_finished is False


def test_parse_standings_fixture():
    rows = parse_standings(load("prev_standings.json"))
    assert [r.rank for r in rows] == list(range(1, 11))
    assert all(r.wins + r.losses + r.ties == 180 for r in rows)
    assert (rows[0].playoff_seed, rows[0].percentage) == (1, 0.661)
    assert all(re.fullmatch(r"Team \d+", r.name) for r in rows)


def standings_body(*team_standings):
    teams = {str(i): {"team": [[{"team_key": f"k.{i}"}, {"team_id": str(i)}, {"name": f"Team {i}"}],
                               {"team_standings": ts}]} for i, ts in enumerate(team_standings)}
    return {"fantasy_content": {"league": [{"league_key": "nba.l.1"},
                                           {"standings": [{"teams": {**teams, "count": len(teams)}}]}]}}


def totals(w=1, l=1, t=0, pct=".500"):
    return {"wins": str(w), "losses": str(l), "ties": str(t), "percentage": pct}


def test_parse_standings_blank_seed_and_rank():
    rows = parse_standings(standings_body(
        {"rank": "", "playoff_seed": "", "outcome_totals": totals()},
        {"rank": 1, "playoff_seed": "2", "outcome_totals": totals(2, 0, 0, "1.000")}))
    assert [(r.team_key, r.rank, r.playoff_seed) for r in rows] == [("k.1", 1, 2), ("k.0", None, None)]
    assert rows[0].percentage == 1.0


@pytest.mark.parametrize("ts", [None, {"rank": 1, "outcome_totals": []}])
def test_parse_standings_malformed_raises(ts):
    body = standings_body({"rank": 1, "outcome_totals": totals()})
    team = body["fantasy_content"]["league"][1]["standings"][0]["teams"]["0"]["team"]
    if ts is None:
        team.pop()
    else:
        team[1] = {"team_standings": ts}
    with pytest.raises(YahooFormatError):
        parse_standings(body)


@pytest.mark.parametrize("raw, expected", [(1, True), ("1", True), (True, True), (0, False), ("0", False), (None, False)])
def test_parse_league_is_finished_forms(raw, expected):
    payload = load("prev_league.json")
    payload["fantasy_content"]["league"][0]["is_finished"] = raw
    assert parse_league(payload).is_finished is expected



# players: fantasy_content.league[1].players = {"0": {"player": [metadata_list, {"ownership": {
#   ownership_type: team|freeagents|waivers, owner_team_key?}}]}, ..., "count": N}

def test_parse_ranked_players_fixture():
    players = parse_ranked_players(load("top_players_0.json"), start=0)
    assert [p.rank for p in players] == list(range(1, 26))
    assert all(p.ownership_type in {"team", "freeagents", "waivers"} for p in players)
    assert all(p.owner_team_key for p in players if p.ownership_type == "team")
    assert all(p.name and p.nba_team and p.position and p.player_key for p in players)


def test_parse_ranked_players_offsets_rank():
    assert parse_ranked_players(load("top_players_25.json"), start=25)[0].rank == 26


def players_body(*players):
    entries = {str(i): {"player": [[{"player_key": f"p.{i}"}, {"name": {"full": f"Player {i}"}},
                                    {"editorial_team_abbr": "SAS"}, {"display_position": "C"}, []],
                                   {"ownership": own}]} for i, own in enumerate(players)}
    return {"fantasy_content": {"league": [{"league_key": "nba.l.1"},
                                           {"players": {**entries, "count": len(entries)}}]}}


@pytest.mark.parametrize("players", [[], None])
def test_parse_ranked_players_empty(players):
    body = players_body()
    if players is None:
        del body["fantasy_content"]["league"][1]["players"]
        body["fantasy_content"]["league"][1] = {"players": []}
    else:
        body["fantasy_content"]["league"][1]["players"] = players
    assert parse_ranked_players(body, start=25) == []


def test_parse_ranked_players_short_page():
    body = players_body({"ownership_type": "team", "owner_team_key": "t.1"},
                        {"ownership_type": "freeagents"}, {"ownership_type": "waivers"})
    players = parse_ranked_players(body, start=25)
    assert [(p.rank, p.ownership_type, p.owner_team_key) for p in players] == [
        (26, "team", "t.1"), (27, "freeagents", None), (28, "waivers", None)]
    assert players[0].name == "Player 0" and players[0].nba_team == "SAS" and players[0].position == "C"


@pytest.mark.parametrize("ownership", [None, {}, {"owner_team_key": "t.1"}])
def test_parse_ranked_players_missing_ownership_raises(ownership):
    """Without ownership every star would silently count as a free agent (and be cached an hour)."""
    body = players_body({"ownership_type": "team", "owner_team_key": "t.1"})
    player = body["fantasy_content"]["league"][1]["players"]["0"]["player"]
    if ownership is None:
        player.pop()
    else:
        player[1] = {"ownership": ownership}
    with pytest.raises(YahooFormatError):
        parse_ranked_players(body, start=0)


@pytest.mark.parametrize("drop", ["name", "player_key"])
def test_parse_ranked_players_malformed_raises(drop):
    body = players_body({"ownership_type": "freeagents"})
    meta = body["fantasy_content"]["league"][1]["players"]["0"]["player"][0]
    meta[:] = [d for d in meta if not (isinstance(d, dict) and drop in d)]
    with pytest.raises(YahooFormatError):
        parse_ranked_players(body, start=0)
