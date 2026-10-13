"""League-level Yahoo reads with the caching policy from spec §5.2.

A week is "current" until it ends, "settling" for 3 days after its end date (Yahoo stat
corrections), and "final" after that. Final data is cached forever.
"""
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from app.cache import Cache, CacheResult
from app.errors import YahooUnavailable
from app.parsing import (GameWeek, LeagueInfo, TeamStats, parse_game_weeks, parse_league,
                         parse_team_stats)

WeekState = Literal["current", "settling", "final"]

CURRENT_TTL = 300
SETTLING_TTL = 3600
FINAL_DELAY_DAYS = 3
PACIFIC = ZoneInfo("America/Los_Angeles")
_CALENDAR_KEY = "game_weeks"


class JsonGetter(Protocol):
    def get_json(self, path: str) -> dict: ...


def pacific_today(now: datetime | None = None) -> date:
    return (now or datetime.now(PACIFIC)).astimezone(PACIFIC).date()


class YahooClient:
    def __init__(self, http: JsonGetter, league_id: str, cache: Cache,
                 today: Callable[[], date] = pacific_today):
        self._http = http
        self._cache = cache
        self._today = today
        self._league_path = f"league/nba.l.{league_id}"

    def league(self, refresh: bool = False) -> tuple[LeagueInfo, CacheResult]:
        result = self._fetch(self._league_path, parse_league, CURRENT_TTL, refresh)
        return result.data, result

    def season_stats(self, refresh: bool = False) -> tuple[list[TeamStats], CacheResult]:
        result = self._fetch(f"{self._league_path}/teams/stats", parse_team_stats, CURRENT_TTL, refresh)
        return result.data, result

    def week_state(self, week: int, current_week: int) -> WeekState:
        if week >= current_week:
            return "current"
        try:
            calendar: dict[int, GameWeek] = self._fetch(
                "game/nba/game_weeks", parse_game_weeks, None, False, key=_CALENDAR_KEY).data
        except YahooUnavailable:
            return "settling"
        game_week = calendar.get(week)
        if game_week is None:
            return "settling"
        return "final" if self._today() > game_week.end + timedelta(days=FINAL_DELAY_DAYS) else "settling"

    def week_stats(self, week: int, current_week: int,
                   refresh: bool = False) -> tuple[list[TeamStats], CacheResult, WeekState]:
        state = self.week_state(week, current_week)
        ttl = {"current": CURRENT_TTL, "settling": SETTLING_TTL, "final": None}[state]
        path = f"{self._league_path}/teams/stats;type=week;week={week}"
        result = self._fetch(path, parse_team_stats, ttl, refresh)
        return result.data, result, state

    def _fetch(self, path: str, parse: Callable[[dict], object], ttl: float | None, refresh: bool,
               key: str | None = None) -> CacheResult:
        return self._cache.get_or_fetch(key or path, lambda: parse(self._http.get_json(path)), ttl, refresh)
