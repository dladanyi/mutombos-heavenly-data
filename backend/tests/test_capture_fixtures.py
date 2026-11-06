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


def test_non_league_payload_passes_through_and_input_is_untouched():
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
