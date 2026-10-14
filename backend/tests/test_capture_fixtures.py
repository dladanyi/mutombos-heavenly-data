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
