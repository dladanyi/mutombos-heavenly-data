import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "capture_fixtures.py"
spec = importlib.util.spec_from_file_location("capture_fixtures", SCRIPT)
capture_fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture_fixtures)


def stats_body(team_meta, league_meta=None):
    return {"fantasy_content": {"xml:lang": "en-US", "league": [
        league_meta or {"league_key": "nba.l.1", "name": "League"},
        {"teams": {"0": {"team": [team_meta, {"team_stats": {"stats": []}, "team_points": {"total": "0"}}]},
                   "count": 1}},
    ]}}


def team_of(body):
    return body["fantasy_content"]["league"][1]["teams"]["0"]["team"]


def test_team_metadata_keeps_only_allowlisted_keys_and_placeholders():
    body = stats_body([
        {"team_key": "k.7"}, {"team_id": "7"}, {"name": "Real Name"}, [], {"url": "https://t"},
        {"team_logos": [{"team_logo": {"url": "https://img"}}]}, {"is_owned_by_current_login": 1},
        {"draft_position": 3}, {"previous_season_team_rank": 9}, {"waiver_priority": 2},
        {"managers": [{"manager": {"nickname": "n", "guid": "G", "email": "e@x"}}]},
    ])
    meta, *rest = team_of(capture_fixtures.anonymise(body))
    assert meta == [{"team_key": "k.7"}, {"team_id": "7"}, {"name": "Team 7"}, []]
    assert rest == [{"team_stats": {"stats": []}}]


def test_league_metadata_keeps_only_allowlisted_keys():
    body = stats_body([{"team_key": "k.1"}, {"team_id": "1"}, {"name": "A"}], league_meta={
        "league_key": "nba.l.1", "league_id": "1", "name": "League", "num_teams": 10,
        "current_week": 3, "start_week": "1", "end_week": "22", "is_finished": 1,
        "url": "https://l", "logo_url": "https://lg", "iris_group_chat_id": "chat"})
    meta = capture_fixtures.anonymise(body)["fantasy_content"]["league"][0]
    assert meta == {"league_key": "nba.l.1", "league_id": "1", "name": "League", "num_teams": 10,
                    "current_week": 3, "start_week": "1", "end_week": "22", "is_finished": 1}


def test_team_without_team_id_fails_loudly():
    body = stats_body([{"team_key": "k.1"}, {"name": "Real Name"}])
    with pytest.raises(ValueError, match="team_id"):
        capture_fixtures.anonymise(body)


def test_game_calendar_passes_through_and_input_is_untouched():
    game = {"fantasy_content": {"game": [{"game_key": "478"}, {"game_weeks": {"count": 0}}]}}
    assert capture_fixtures.anonymise(game) == game
    body = stats_body([{"team_key": "k.1"}, {"team_id": "1"}, {"name": "Real Name"}])
    capture_fixtures.anonymise(body)
    assert team_of(body)[0][2] == {"name": "Real Name"}


def test_unknown_league_part_fails_loudly():
    body = stats_body([{"team_key": "k.1"}, {"team_id": "1"}, {"name": "A"}])
    body["fantasy_content"]["league"].append({"standings": [{"managers": [{"manager": {"email": "e@x"}}]}]})
    with pytest.raises(ValueError, match="standings"):
        capture_fixtures.anonymise(body)


def test_league_that_is_not_a_list_fails_loudly():
    with pytest.raises(ValueError, match="league"):
        capture_fixtures.anonymise({"fantasy_content": {"league": {"league_key": "k", "name": "L"}}})


def test_payload_without_league_or_calendar_fails_loudly():
    users = {"fantasy_content": {"users": {"0": {"user": [{"guid": "G"}, {"games": {}}]}}}}
    with pytest.raises(ValueError, match="users"):
        capture_fixtures.anonymise(users)
    with pytest.raises(ValueError):
        capture_fixtures.anonymise({"error": "nope"})


def test_game_with_more_than_the_calendar_fails_loudly():
    game = {"fantasy_content": {"game": [{"game_key": "478"}, {"leagues": {"count": 1}}]}}
    with pytest.raises(ValueError, match="game"):
        capture_fixtures.anonymise(game)


def test_name_sharing_a_dict_with_team_key_keeps_both():
    body = stats_body([{"team_key": "k.1", "name": "Real Name"}, {"team_id": "1"}])
    meta = team_of(capture_fixtures.anonymise(body))[0]
    assert meta == [{"team_key": "k.1", "name": "Team 1"}, {"team_id": "1"}]


def test_siblings_of_teams_and_team_entries_are_dropped():
    body = stats_body([{"team_key": "k.1"}, {"team_id": "1"}, {"name": "A"}])
    teams_part = body["fantasy_content"]["league"][1]
    teams_part["managers"] = [{"email": "e@x"}]
    teams_part["teams"]["0"]["team_owner"] = {"guid": "G"}
    clean = capture_fixtures.anonymise(body)
    assert clean["fantasy_content"]["league"][1].keys() == {"teams"}
    assert clean["fantasy_content"]["league"][1]["teams"]["0"].keys() == {"team"}
    assert "e@x" not in repr(clean) and "G" not in repr(clean)


def test_unknown_top_level_key_is_dropped():
    body = stats_body([{"team_key": "k.1"}, {"team_id": "1"}, {"name": "A"}])
    body["fantasy_content"]["users"] = {"0": {"user": [{"guid": "G"}]}}
    clean = capture_fixtures.anonymise(body)
    assert set(clean["fantasy_content"]) == {"xml:lang", "league"}


@pytest.mark.parametrize("teams", [[], {"0": {"not_team": []}, "count": 1}, {"0": {"team": {}}, "count": 1}])
def test_malformed_teams_fail_with_value_error(teams):
    body = stats_body([{"team_key": "k.1"}, {"team_id": "1"}, {"name": "A"}])
    body["fantasy_content"]["league"][1]["teams"] = teams
    with pytest.raises(ValueError):
        capture_fixtures.anonymise(body)


def scoreboard_body(matchup_extra=None, scoreboard_extra=None):
    team = lambda n: {"team": [[{"team_key": f"k.{n}"}, {"team_id": str(n)}, {"name": f"Real {n}"},
                                {"managers": [{"manager": {"email": "e@x"}}]}],
                               {"team_stats": {"stats": []}, "team_points": {"total": "5"}}]}
    matchup = {"week": "3", "status": "postevent", "is_tied": 0, "winner_team_key": "k.1",
               "is_matchup_of_the_week": "1", "matchup_recap_url": "https://recap",
               "stat_winners": [{"stat_winner": {"stat_id": "12", "winner_team_key": "k.1", "extra": 1}},
                                {"stat_winner": {"stat_id": "17", "is_tied": 1}}],
               "0": {"teams": {"0": team(1), "1": team(2), "count": 2}}, **(matchup_extra or {})}
    return {"fantasy_content": {"league": [
        {"league_key": "nba.l.1", "name": "League"},
        {"scoreboard": {"week": 3, "0": {"matchups": {"0": {"matchup": matchup}, "count": 1}}, **(scoreboard_extra or {})}},
    ]}}


def test_scoreboard_keeps_results_and_anonymises_teams():
    out = capture_fixtures.anonymise(scoreboard_body())["fantasy_content"]["league"][1]["scoreboard"]
    matchup = out["0"]["matchups"]["0"]["matchup"]
    assert out["week"] == 3 and out["0"]["matchups"]["count"] == 1
    assert set(matchup) == {"week", "status", "is_tied", "winner_team_key", "stat_winners", "0"}
    assert matchup["stat_winners"] == [{"stat_winner": {"stat_id": "12", "winner_team_key": "k.1"}},
                                       {"stat_winner": {"stat_id": "17", "is_tied": 1}}]
    teams = matchup["0"]["teams"]
    assert teams["0"]["team"] == [[{"team_key": "k.1"}, {"team_id": "1"}, {"name": "Team 1"}],
                                  {"team_stats": {"stats": []}}]
    assert "e@x" not in repr(out) and "Real" not in repr(out)


@pytest.mark.parametrize("body", [
    scoreboard_body(scoreboard_extra={"standings": []}),
    scoreboard_body(matchup_extra={"0": {"teams": {}, "managers": []}}),
])
def test_unknown_scoreboard_shapes_fail_loudly(body):
    with pytest.raises(ValueError):
        capture_fixtures.anonymise(body)
