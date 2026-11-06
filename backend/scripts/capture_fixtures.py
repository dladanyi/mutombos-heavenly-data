"""Save live Yahoo responses to backend/tests/fixtures/ for the test suite.

Run from the repo root:
    set -a; source .env; set +a
    .venv/bin/python backend/scripts/capture_fixtures.py
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings  # noqa: E402
from app.yahoo_http import YahooHttp  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

# The repo is public, so league and team metadata are filtered through ALLOWLISTS: a field
# Yahoo adds later is dropped unless it's listed here. Team metadata carries the personal data
# (managers, logos, is_owned_by_current_login, draft position, ...); parsing.py reads only
# team_key and name. The league list adds num_teams/season for tests and is_finished for when
# Yahoo sends it. game_weeks (Yahoo's public NBA calendar) is saved as returned.
TEAM_META_KEEP = {"team_key", "team_id", "name"}
TEAM_PARTS_KEEP = {"team_stats"}
LEAGUE_META_KEEP = {"league_key", "league_id", "name", "season", "num_teams", "current_week",
                    "start_week", "end_week", "start_date", "end_date", "is_finished"}


def anonymise(body: dict) -> dict:
    """Return a copy of a Yahoo response with league and team metadata reduced to the
    allowlists and each team renamed to "Team <team_id>". The game_weeks calendar (public)
    passes through unchanged. Any other shape raises, e.g. a league part other than the
    metadata or `teams` (standings, scoreboard) or a `users` payload: it may carry team or
    manager blocks the allowlists haven't been written for."""
    body = copy.deepcopy(body)
    content = body.get("fantasy_content")
    if not isinstance(content, dict):
        raise ValueError("response has no fantasy_content")
    if "league" not in content:
        if _is_game_calendar(content):
            return body
        raise ValueError(f"unknown response shape {sorted(content)}; add an allowlist for it before capturing")
    league = content["league"]
    if not isinstance(league, list):
        raise ValueError(f"unexpected league of type {type(league).__name__}")
    for i, part in enumerate(league):
        if not isinstance(part, dict):
            raise ValueError(f"unexpected league part of type {type(part).__name__}")
        if "league_key" in part:
            league[i] = {k: v for k, v in part.items() if k in LEAGUE_META_KEEP}
        elif "teams" in part:
            for key, entry in part["teams"].items():
                if key != "count":
                    entry["team"] = _anonymise_team(entry["team"])
        else:
            raise ValueError(f"unknown league part {sorted(part)}; add an allowlist for it before capturing")
    return body


def _is_game_calendar(content: dict) -> bool:
    """True for game/nba/game_weeks: a `game` list of the game's metadata plus `game_weeks`."""
    game = content.get("game")
    if "users" in content or not isinstance(game, list):
        return False
    parts = [set(p) for p in game if isinstance(p, dict)]
    return len(parts) == len(game) == 2 and "game_key" in parts[0] and parts[1] == {"game_weeks"}


def _anonymise_team(team: list) -> list:
    """`team` is [metadata_list, {"team_stats": ...}, ...]. The metadata list mixes single-key
    dicts with empty-list placeholders; keep the placeholders so the parser still sees them."""
    meta_list, *parts = team
    team_id = next((d["team_id"] for d in meta_list if isinstance(d, dict) and "team_id" in d), None)
    if team_id is None:
        raise ValueError("team metadata has no team_id; Yahoo's shape changed, so refusing to save it")
    kept_meta = []
    for item in meta_list:
        if item == []:
            kept_meta.append(item)
        elif isinstance(item, dict) and item.keys() & TEAM_META_KEEP:
            kept = {k: v for k, v in item.items() if k in TEAM_META_KEEP}
            if "name" in kept:
                kept["name"] = f"Team {team_id}"
            kept_meta.append(kept)
    kept_parts = [{k: v for k, v in p.items() if k in TEAM_PARTS_KEEP}
                  for p in parts if isinstance(p, dict) and p.keys() & TEAM_PARTS_KEEP]
    return [kept_meta, *kept_parts]


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
    # Anonymise and write every file to a temp name first, then rename them all, so a shape or
    # write error leaves the old fixture set intact. (The renames themselves aren't one atomic
    # step; an interrupt between them could still mix sets. *.tmp is git-ignored.)
    cleaned = {name: anonymise(body) for name, body in responses.items()}
    FIXTURES.mkdir(parents=True, exist_ok=True)
    temps = {}
    try:
        for name, body in cleaned.items():
            temps[name] = FIXTURES / f"{name}.tmp"
            temps[name].write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
    except BaseException:
        for tmp in temps.values():
            tmp.unlink(missing_ok=True)
        raise
    for name, tmp in temps.items():
        tmp.replace(FIXTURES / name)
        print(f"{name}: {(FIXTURES / name).stat().st_size} bytes")
    print(f"week_stats.json is week {week} (current week {current_week})")


if __name__ == "__main__":
    main()
