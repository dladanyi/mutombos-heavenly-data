"""Star Power: how many of each team's players are in the season-to-date top 10, 25 and 50."""
from app.parsing import RankedPlayer, TeamStats

LEVELS = (10, 25, 50)


def build_star_power(players: list[RankedPlayer], teams: list[TeamStats]) -> dict:
    """Teams ordered by top-10 count, then top-25, then top-50 (cumulative), then name.
    Ties share a place. Top-50 players on no known team are listed under "unowned"."""
    top = sorted((p for p in players if p.rank <= LEVELS[-1]), key=lambda p: p.rank)
    known = {t.team_key for t in teams}
    by_team: dict[str, list[RankedPlayer]] = {t.team_key: [] for t in teams}
    unowned = []
    for p in top:
        if p.ownership_type == "team" and p.owner_team_key in known:
            by_team[p.owner_team_key].append(p)
        else:  # free agents, waivers, or an owner team the league list doesn't have
            unowned.append({**_player_json(p), "status": p.ownership_type})

    rows = []
    for t in teams:
        ranks = [p.rank for p in by_team[t.team_key]]
        counts = {str(level): sum(r <= level for r in ranks) for level in LEVELS}
        rows.append({"team_key": t.team_key, "name": t.name, "counts": counts,
                     "players": [_player_json(p) for p in by_team[t.team_key]]})

    def strength(row: dict) -> tuple[int, ...]:
        return tuple(row["counts"][str(level)] for level in LEVELS)

    rows.sort(key=lambda r: (tuple(-c for c in strength(r)), r["name"]))
    for row in rows:
        row["place"] = 1 + sum(strength(other) > strength(row) for other in rows)
    return {"teams": [{"team_key": r["team_key"], "name": r["name"], "place": r["place"],
                       "counts": r["counts"], "players": r["players"]} for r in rows],
            "unowned": unowned}


def _player_json(p: RankedPlayer) -> dict:
    return {"rank": p.rank, "player_key": p.player_key, "name": p.name, "nba_team": p.nba_team,
            "position": p.position}
