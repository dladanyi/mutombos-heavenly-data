"""Generate SYNTHETIC Yahoo responses in the Fantasy API's JSON shape.

Yahoo blocked this app's Fantasy API access (2026-07 access-program change), so real responses
could not be captured. These files follow the shape the old app.py parsed in production
(league[0] metadata, league[1].teams.N.team = [metadata list, {team_stats}]) and the
game_weeks shape documented by yfpy. Replace them with real captures from
backend/scripts/capture_fixtures.py once Yahoo approves access, then delete this script.

Run: .venv/bin/python backend/tests/fixtures/make_synthetic.py
"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEAGUE_ID = "46425"
GAME_KEY = "466"
LEAGUE_KEY = f"{GAME_KEY}.l.{LEAGUE_ID}"
CURRENT_WEEK = 7
STAT_WEEK = 6
TEAM_NAMES = [
    "Finger Wag Factory", "No No No", "Swat Team", "Rim Protectors", "Glass Cleaners",
    "Paint Patrol", "Block Party Crashers", "Mount Mutombo", "Denied!", "Weak Side Help",
    "Goaltenders", "Help Defense",
]


def game_weeks() -> list[tuple[int, date, date]]:
    weeks = [(1, date(2026, 10, 20), date(2026, 10, 26))]
    start = date(2026, 10, 27)
    for week in range(2, 25):
        weeks.append((week, start, start + timedelta(days=6)))
        start += timedelta(days=7)
    return weeks


def league_meta() -> dict:
    return {
        "league_key": LEAGUE_KEY, "league_id": LEAGUE_ID, "name": "Mutombo's Heavenly Block Party",
        "url": f"https://basketball.fantasysports.yahoo.com/nba/{LEAGUE_ID}", "logo_url": False,
        "draft_status": "postdraft", "num_teams": len(TEAM_NAMES), "edit_key": "2026-12-01",
        "weekly_deadline": "intraday", "scoring_type": "head", "league_type": "private",
        "renew": "454_11070", "renewed": "", "is_pro_league": "0", "is_cash_league": "0",
        "current_week": CURRENT_WEEK, "start_week": "1", "start_date": "2026-10-20",
        "end_week": "21", "end_date": "2027-03-21", "game_code": "nba", "season": "2026",
    }


def team_stats(rng: random.Random, scale: int) -> list[dict]:
    fga = rng.randint(70, 95) * scale
    fgm = int(fga * rng.uniform(0.43, 0.51))
    fta = rng.randint(18, 30) * scale
    ftm = int(fta * rng.uniform(0.70, 0.85))
    values = {
        "9004003": f"{fgm}/{fga}", "5": f"{fgm / fga:.3f}".lstrip("0"),
        "9007006": f"{ftm}/{fta}", "8": f"{ftm / fta:.3f}".lstrip("0"),
        "10": str(rng.randint(10, 17) * scale), "12": str(rng.randint(100, 125) * scale),
        "15": str(rng.randint(40, 55) * scale), "16": str(rng.randint(22, 32) * scale),
        "17": str(rng.randint(6, 11) * scale), "18": str(rng.randint(4, 9) * scale),
        "19": str(rng.randint(12, 18) * scale),
    }
    return [{"stat": {"stat_id": sid, "value": v}} for sid, v in values.items()]


def team(index: int, name: str, stats: list[dict], coverage: dict) -> dict:
    team_id = str(index + 1)
    metadata = [
        {"team_key": f"{LEAGUE_KEY}.t.{team_id}"}, {"team_id": team_id}, {"name": name}, [],
        {"url": f"https://basketball.fantasysports.yahoo.com/nba/{LEAGUE_ID}/{team_id}"},
        {"team_logos": [{"team_logo": {"size": "large", "url": "https://example.invalid/logo.png"}}]},
        [], {"waiver_priority": index + 1}, [], {"number_of_moves": "4"},
        {"number_of_trades": 0}, {"roster_adds": {"coverage_type": "week", "coverage_value": "7", "value": "1"}},
        [], {"league_scoring_type": "head"}, [], [], {"has_draft_grade": 0}, [], [],
        {"managers": [{"manager": {"manager_id": team_id, "nickname": "--hidden--", "guid": "SYNTHETIC"}}]},
    ]
    return {"team": [metadata, {"team_stats": {**coverage, "stats": stats}}]}


def stats_response(seed: int, scale: int, coverage: dict, uri: str) -> dict:
    rng = random.Random(seed)
    teams = {str(i): team(i, name, team_stats(rng, scale), coverage) for i, name in enumerate(TEAM_NAMES)}
    teams["count"] = len(TEAM_NAMES)
    return wrap(uri, {"league": [league_meta(), {"teams": teams}]})


def wrap(uri: str, content: dict) -> dict:
    return {"fantasy_content": {"xml:lang": "en-US", "yahoo:uri": uri, **content,
                                "time": "41.2ms", "copyright": "Data provided by Yahoo! and STATS, LLC",
                                "refresh_rate": "60"}}


def main() -> None:
    weeks = {str(i): {"game_week": {"week": str(w), "display_name": str(w), "start": s.isoformat(),
                                    "end": e.isoformat()}}
             for i, (w, s, e) in enumerate(game_weeks())}
    weeks["count"] = len(weeks)
    game_meta = {"game_key": GAME_KEY, "game_id": GAME_KEY, "name": "Basketball", "code": "nba",
                 "type": "full", "url": "https://basketball.fantasysports.yahoo.com/nba", "season": "2026",
                 "is_registration_over": 0, "is_game_over": 0, "is_offseason": 0}
    files = {
        "league.json": wrap(f"/fantasy/v2/league/nba.l.{LEAGUE_ID}", {"league": [league_meta()]}),
        "season_stats.json": stats_response(1, CURRENT_WEEK - 1, {"coverage_type": "season", "season": "2026"},
                                            f"/fantasy/v2/league/nba.l.{LEAGUE_ID}/teams/stats"),
        "week_stats.json": stats_response(2, 1, {"coverage_type": "week", "week": str(STAT_WEEK)},
                                          f"/fantasy/v2/league/nba.l.{LEAGUE_ID}/teams/stats;type=week;week={STAT_WEEK}"),
        "game_weeks.json": wrap("/fantasy/v2/game/nba/game_weeks", {"game": [game_meta, {"game_weeks": weeks}]}),
    }
    for name, body in files.items():
        (HERE / name).write_text(json.dumps(body, indent=2) + "\n")
        print(name)


if __name__ == "__main__":
    main()
