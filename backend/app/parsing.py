"""Turn Yahoo Fantasy API JSON into small typed records.

Fields are located by key name, never by list position, because Yahoo returns many objects as
lists of single-key dicts (mixed with empty lists) whose order isn't guaranteed.
"""
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from app.errors import YahooFormatError


@dataclass(frozen=True)
class TeamStats:
    team_key: str
    name: str
    values: dict[str, str | None]  # keyed by Yahoo stat_id


@dataclass(frozen=True)
class LeagueInfo:
    name: str
    current_week: int
    start_week: int
    end_week: int
    league_key: str = ""
    season: int | None = None
    previous_league_key: str | None = None  # from `renew`, e.g. "466_11070" -> "466.l.11070"
    is_finished: bool = False


@dataclass(frozen=True)
class Standing:
    rank: int | None  # final finish (after the playoffs); None if Yahoo sends it blank
    team_key: str
    name: str
    wins: int
    losses: int
    ties: int
    percentage: float | None
    playoff_seed: int | None


@dataclass(frozen=True)
class GameWeek:
    week: int
    start: date
    end: date


@dataclass(frozen=True)
class MatchupResult:
    """One team's side of a head-to-head week. Category counts are from this team's view."""
    outcome: Literal["W", "L", "T"] | None  # None until Yahoo marks the matchup finished
    wins: int
    losses: int
    ties: int
    opponent_key: str
    opponent_name: str


def parse_league(payload: dict) -> LeagueInfo:
    meta = _first_dict(_get(payload, "fantasy_content", "league"), "league")
    try:
        renew = str(meta.get("renew") or "")
        return LeagueInfo(
            name=str(meta["name"]),
            current_week=int(meta["current_week"]),
            start_week=int(meta["start_week"]),
            end_week=int(meta["end_week"]),
            league_key=str(meta.get("league_key", "")),
            season=int(meta["season"]) if meta.get("season") not in (None, "") else None,
            previous_league_key=renew.replace("_", ".l.", 1) if "_" in renew else None,
            is_finished=str(meta.get("is_finished")) == "1",
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise YahooFormatError(f"league metadata is missing or invalid: {exc}") from exc


def parse_team_stats(payload: dict) -> list[TeamStats]:
    league = _get(payload, "fantasy_content", "league")
    teams_container = _find_dict_with(league, "teams", "league")["teams"]
    teams = []
    for key, value in _indexed(teams_container, "teams"):
        teams.append(_parse_team(_get(value, "team"), f"teams.{key}"))
    return teams


def parse_game_weeks(payload: dict) -> dict[int, GameWeek]:
    game = _get(payload, "fantasy_content", "game")
    container = _find_dict_with(game, "game_weeks", "game")["game_weeks"]
    weeks = {}
    for key, value in _indexed(container, "game_weeks"):
        raw = _get(value, "game_week")
        try:
            week = GameWeek(int(raw["week"]), date.fromisoformat(raw["start"]), date.fromisoformat(raw["end"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise YahooFormatError(f"game_weeks.{key} is invalid: {exc}") from exc
        weeks[week.week] = week
    return weeks


def parse_scoreboard(payload: dict) -> dict[str, MatchupResult]:
    """Map each team_key in the week's matchups to its result. Teams without a matchup (playoff
    byes, or a week whose matchups aren't set yet) are absent."""
    league = _get(payload, "fantasy_content", "league")
    scoreboard = _find_dict_with(league, "scoreboard", "league")["scoreboard"]
    holder = _get(scoreboard, "0")
    matchups = holder.get("matchups") if isinstance(holder, dict) else None
    if not isinstance(matchups, dict):  # Yahoo sends [] or leaves it out when there are none
        return {}
    results: dict[str, MatchupResult] = {}
    for key, value in _indexed(matchups, "matchups"):
        results.update(_parse_matchup(_get(value, "matchup"), f"matchups.{key}"))
    return results


def _parse_matchup(matchup: dict, where: str) -> dict[str, MatchupResult]:
    teams = [_team_metadata(_get(value, "team"), f"{where}.teams.{key}")
             for key, value in _indexed(_get(matchup, "0", "teams"), f"{where}.teams")]
    if len(teams) != 2:
        raise YahooFormatError(f"{where} has {len(teams)} teams, expected 2")
    (a_key, a_name), (b_key, b_name) = teams
    wins = {a_key: 0, b_key: 0}
    ties = 0
    stat_winners = matchup.get("stat_winners", [])  # absent = no categories decided yet
    if not isinstance(stat_winners, list):
        raise YahooFormatError(f"{where}.stat_winners is not a list")
    for entry in stat_winners:
        winner = _get(entry, "stat_winner")
        if not isinstance(winner, dict):
            raise YahooFormatError(f"{where} has a malformed stat winner: {winner!r}")
        if str(winner.get("is_tied")) == "1":
            ties += 1
        elif winner.get("winner_team_key") in wins:
            wins[winner["winner_team_key"]] += 1
        else:
            raise YahooFormatError(f"{where} has a stat winner outside the matchup: {winner}")
    finished = matchup.get("status") == "postevent"
    tied = str(matchup.get("is_tied")) == "1"
    winner = matchup.get("winner_team_key")

    def outcome(key: str):
        if not finished:
            return None
        if tied:
            return "T"
        return None if winner not in wins else "W" if winner == key else "L"

    return {
        a_key: MatchupResult(outcome(a_key), wins[a_key], wins[b_key], ties, b_key, b_name),
        b_key: MatchupResult(outcome(b_key), wins[b_key], wins[a_key], ties, a_key, a_name),
    }


def _merged_metadata(team: list) -> dict[str, Any]:
    """Yahoo's team metadata is a list of single-key dicts (and empty lists); merge them."""
    metadata: dict[str, Any] = {}
    for part in team:
        if isinstance(part, list):
            for item in part:
                if isinstance(item, dict):
                    metadata.update(item)
    return metadata


def _team_metadata(team: Any, where: str) -> tuple[str, str]:
    if not isinstance(team, list):
        raise YahooFormatError(f"{where}.team is not a list")
    metadata = _merged_metadata(team)
    if "team_key" not in metadata or "name" not in metadata:
        raise YahooFormatError(f"{where} is missing team_key or name")
    return str(metadata["team_key"]), str(metadata["name"])


def parse_standings(payload: dict) -> list[Standing]:
    """Final standings, sorted by rank (blank ranks last)."""
    league = _get(payload, "fantasy_content", "league")
    standings = _find_dict_with(league, "standings", "league")["standings"]
    teams_container = _get(_first_dict(standings, "standings"), "teams")
    rows = []
    for key, value in _indexed(teams_container, "standings.teams"):
        where = f"standings.teams.{key}"
        team = _get(value, "team")
        team_key, name = _team_metadata(team, where)
        holder = next((p["team_standings"] for p in team if isinstance(p, dict) and "team_standings" in p), None)
        totals = holder.get("outcome_totals") if isinstance(holder, dict) else None
        if not isinstance(totals, dict):
            raise YahooFormatError(f"{where} is missing team_standings.outcome_totals")
        try:
            rows.append(Standing(
                rank=_optional_int(holder.get("rank")), team_key=team_key, name=name,
                wins=int(totals["wins"]), losses=int(totals["losses"]), ties=int(totals.get("ties") or 0),
                percentage=float(totals["percentage"]) if totals.get("percentage") not in (None, "") else None,
                playoff_seed=_optional_int(holder.get("playoff_seed"))))
        except (KeyError, TypeError, ValueError) as exc:
            raise YahooFormatError(f"{where} has malformed standings: {exc}") from exc
    return sorted(rows, key=lambda r: (r.rank is None, r.rank or 0))


def _optional_int(raw: Any) -> int | None:
    return None if raw in (None, "", "-") else int(raw)


def _parse_team(team: Any, where: str) -> TeamStats:
    if not isinstance(team, list):
        raise YahooFormatError(f"{where}.team is not a list")
    metadata = _merged_metadata(team)
    stats_holder = next((p["team_stats"] for p in team if isinstance(p, dict) and "team_stats" in p), None)
    if "team_key" not in metadata or "name" not in metadata or stats_holder is None:
        raise YahooFormatError(f"{where} is missing team_key, name or team_stats")

    values: dict[str, str | None] = {}
    for entry in _get(stats_holder, "stats"):
        stat = _get(entry, "stat")
        try:
            raw = stat["value"]
            values[str(stat["stat_id"])] = None if raw is None else str(raw)
        except (KeyError, TypeError) as exc:
            raise YahooFormatError(f"{where} has a malformed stat: {exc}") from exc
    return TeamStats(team_key=str(metadata["team_key"]), name=str(metadata["name"]), values=values)


def _get(obj: Any, *keys: str) -> Any:
    path = []
    for key in keys:
        path.append(key)
        if not isinstance(obj, dict) or key not in obj:
            raise YahooFormatError(f"missing {'.'.join(path)}")
        obj = obj[key]
    return obj


def _first_dict(items: Any, where: str) -> dict:
    if isinstance(items, dict):
        return items
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                return item
    raise YahooFormatError(f"{where} has no object")


def _find_dict_with(items: Any, key: str, where: str) -> dict:
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and key in item:
                return item
    raise YahooFormatError(f"{where} has no {key}")


def _indexed(container: Any, where: str):
    """Yield (key, value) for Yahoo's {"0": ..., "1": ..., "count": N} collections, in index order."""
    if not isinstance(container, dict):
        raise YahooFormatError(f"{where} is not an object")
    keys = sorted((k for k in container if k.isdigit()), key=int)
    for key in keys:
        yield key, container[key]
