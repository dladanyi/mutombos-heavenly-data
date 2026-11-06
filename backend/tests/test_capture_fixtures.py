import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "capture_fixtures.py"
spec = importlib.util.spec_from_file_location("capture_fixtures", SCRIPT)
capture_fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture_fixtures)


def test_strip_private_removes_managers_at_any_depth():
    body = {"fantasy_content": {"league": [
        {"name": "L"},
        {"teams": {"0": {"team": [[
            {"team_key": "k.1"}, {"name": "Alpha"},
            {"managers": [{"manager": {"nickname": "n", "guid": "G", "email": "e@x"}}]},
        ]]}, "count": 1}},
    ]}}
    clean = capture_fixtures.strip_private(body)
    assert "managers" not in repr(clean)
    assert "e@x" not in repr(clean)
    team = clean["fantasy_content"]["league"][1]["teams"]["0"]["team"][0]
    assert team == [{"team_key": "k.1"}, {"name": "Alpha"}, {}]


def test_strip_private_anonymises_teams_and_drops_links():
    body = {"fantasy_content": {"league": [
        {"name": "League", "league_id": "1", "url": "https://l", "logo_url": "https://lg",
         "iris_group_chat_id": "chat"},
        {"teams": {"0": {"team": [[
            {"team_key": "k.7"}, {"team_id": "7"}, {"name": "Real Name"}, {"url": "https://t"},
            {"team_logos": [{"team_logo": {"size": "large", "url": "https://img"}}]},
        ]]}, "count": 1}},
    ]}}
    clean = capture_fixtures.strip_private(body)
    meta, team = clean["fantasy_content"]["league"][0], clean["fantasy_content"]["league"][1]["teams"]["0"]["team"][0]
    assert meta == {"name": "League", "league_id": "1"}
    assert team == [{"team_key": "k.7"}, {"team_id": "7"}, {"name": "Team 7"}, {}, {}]
    assert "https://" not in repr(clean) and "Real Name" not in repr(clean)
