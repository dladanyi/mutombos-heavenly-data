"""Save live Yahoo responses to backend/tests/fixtures/ for the test suite.

Run from the repo root:
    set -a; source .env; set +a
    .venv/bin/python backend/scripts/capture_fixtures.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings  # noqa: E402
from app.yahoo_http import YahooHttp  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
# The repo is public: drop each team's managers block (nickname, GUID, possibly an email).
PRIVATE_KEYS = {"managers"}


def strip_private(value):
    """Return `value` with every PRIVATE_KEYS entry removed, at any depth."""
    if isinstance(value, dict):
        return {k: strip_private(v) for k, v in value.items() if k not in PRIVATE_KEYS}
    if isinstance(value, list):
        return [strip_private(v) for v in value]
    return value


def main() -> None:
    settings = load_settings()
    http = YahooHttp(settings.consumer_key, settings.consumer_secret, settings.refresh_token)
    league_key = f"nba.l.{settings.league_id}"

    league = http.get_json(f"league/{league_key}")
    meta = league["fantasy_content"]["league"][0]
    current_week = int(meta["current_week"])
    start_week = int(meta["start_week"])
    week = current_week - 1 if current_week > start_week else current_week

    responses = {
        "league.json": league,
        "season_stats.json": http.get_json(f"league/{league_key}/teams/stats"),
        "week_stats.json": http.get_json(f"league/{league_key}/teams/stats;type=week;week={week}"),
        "game_weeks.json": http.get_json("game/nba/game_weeks"),
    }
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, body in responses.items():
        path = FIXTURES / name
        path.write_text(json.dumps(strip_private(body), indent=2, ensure_ascii=False) + "\n")
        print(f"{name}: {path.stat().st_size} bytes")
    print(f"week_stats.json is week {week} (current week {current_week})")


if __name__ == "__main__":
    main()
