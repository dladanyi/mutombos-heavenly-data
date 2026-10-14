"""Turn Yahoo Fantasy API JSON into small typed records.

Fields are located by key name, never by list position, because Yahoo returns many objects as
lists of single-key dicts (mixed with empty lists) whose order isn't guaranteed.
"""
from dataclasses import dataclass
from datetime import date
from typing import Any

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


@dataclass(frozen=True)
class GameWeek:
    week: int
    start: date
    end: date


def parse_league(payload: dict) -> LeagueInfo:
    meta = _first_dict(_get(payload, "fantasy_content", "league"), "league")
    try:
        return LeagueInfo(
            name=str(meta["name"]),
            current_week=int(meta["current_week"]),
            start_week=int(meta["start_week"]),
            end_week=int(meta["end_week"]),
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


def _parse_team(team: Any, where: str) -> TeamStats:
    if not isinstance(team, list):
        raise YahooFormatError(f"{where}.team is not a list")
    metadata: dict[str, Any] = {}
    stats_holder = None
    for part in team:
        if isinstance(part, list):
            for item in part:
                if isinstance(item, dict):
                    metadata.update(item)
        elif isinstance(part, dict) and "team_stats" in part:
            stats_holder = part["team_stats"]
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
