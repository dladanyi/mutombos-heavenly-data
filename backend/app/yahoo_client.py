"""League-level Yahoo reads with the caching policy from spec §5.2.

A week is "current" until it ends, "settling" for 3 days after its end date (Yahoo stat
corrections), and "final" after that. Final data is cached forever. After the season Yahoo leaves
`current_week` on the last week, so that week also goes by its calendar end date.
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from app.cache import Cache, CacheResult
from app.errors import YahooAccessDenied, YahooUnavailable
from app.parsing import (GameWeek, LeagueInfo, MatchupResult, RankedPlayer, Standing, TeamStats,
                         parse_game_weeks, parse_league, parse_ranked_players, parse_scoreboard,
                         parse_standings, parse_team_stats)

WeekState = Literal["current", "settling", "final"]

CURRENT_TTL = 300
SETTLING_TTL = 3600
FINAL_DELAY_DAYS = 3
PACIFIC = ZoneInfo("America/Los_Angeles")
_CALENDAR_KEY = "game_weeks"
TOP_PLAYERS_TTL = 3600  # Yahoo updates season ranks about daily
TOP_PLAYERS_PAGES = (0, 25)  # Yahoo returns at most 25 players per call
PREVIOUS_LEAGUE_TTL = 86400  # also how long a 403 ("no access to that season") stop is remembered
MAX_SEASONS = 20  # loop guard for the renew walk
_WEEK_TTL: dict[str, float | None] = {"current": CURRENT_TTL, "settling": SETTLING_TTL, "final": None}


@dataclass(frozen=True)
class SeasonRef:
    season: int
    league_key: str
    current: bool
    finished: bool


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
        # Without a calendar date, a week Yahoo calls current stays current and a past week settles.
        fallback: WeekState = "current" if week >= current_week else "settling"
        try:
            calendar: dict[int, GameWeek] = self._fetch(
                "game/nba/game_weeks", parse_game_weeks, None, False, key=_CALENDAR_KEY).data
        except YahooUnavailable:
            return fallback
        game_week = calendar.get(week)
        if game_week is None:
            return fallback
        today = self._today()
        if today <= game_week.end:
            return fallback
        return "final" if today > game_week.end + timedelta(days=FINAL_DELAY_DAYS) else "settling"

    def week_stats(self, week: int, current_week: int,
                   refresh: bool = False) -> tuple[list[TeamStats], CacheResult, WeekState]:
        state = self.week_state(week, current_week)
        path = f"{self._league_path}/teams/stats;type=week;week={week}"
        result = self._fetch(path, parse_team_stats, _WEEK_TTL[state], refresh)
        return result.data, result, state

    def week_results(self, week: int, state: WeekState,
                     refresh: bool = False) -> tuple[dict[str, MatchupResult], CacheResult]:
        """Head-to-head results by team_key. Pass the state week_stats returned, so the stats and
        the scoreboard are cached under the same state (and the calendar isn't looked up twice)."""
        path = f"{self._league_path}/scoreboard;week={week}"
        result = self._fetch(path, parse_scoreboard, _WEEK_TTL[state], refresh)
        return result.data, result

    def top_players(self, refresh: bool = False) -> tuple[list[RankedPlayer], CacheResult]:
        """Season-to-date top 50 with ownership. Both pages are fetched inside one cached fetch,
        so a failure on either page caches nothing (never half a list for an hour)."""
        def fetch() -> list[RankedPlayer]:
            players: list[RankedPlayer] = []
            for start in TOP_PLAYERS_PAGES:
                path = (f"{self._league_path}/players;sort=AR;sort_type=season;"
                        f"start={start};count=25/ownership")
                players.extend(parse_ranked_players(self._http.get_json(path), start))
            return players
        result = self._cache.get_or_fetch(f"{self._league_path}/players:top50", fetch, TOP_PLAYERS_TTL, refresh)
        return result.data, result

    def standings(self, refresh: bool = False) -> tuple[list[Standing], CacheResult]:
        """The current league's standings (records cover completed weeks)."""
        result = self._fetch(f"{self._league_path}/standings", parse_standings, CURRENT_TTL, refresh)
        return result.data, result

    def seasons(self, refresh: bool = False) -> tuple[list[SeasonRef], bool, list[CacheResult]]:
        """Readable seasons, newest first, by following each league's `renew` link. Returns
        (seasons, complete, results): `complete` is False when an outage cut the walk short."""
        info, current_result = self.league(refresh=refresh)
        current_key = info.league_key or self._league_path.removeprefix("league/")
        seasons = [SeasonRef(info.season or 0, current_key, True, info.is_finished)]
        results = [current_result]
        key = info.previous_league_key
        complete = True
        while key and len(seasons) < MAX_SEASONS:
            try:
                result = self._cache.get_or_fetch(f"league/{key}", self._league_or_denied(key),
                                                  PREVIOUS_LEAGUE_TTL)
            except YahooUnavailable:
                complete = False
                break
            if result.data is None:  # 403: this account can't read that season; end of history
                break
            results.append(result)
            prev: LeagueInfo = result.data
            seasons.append(SeasonRef(prev.season or 0, prev.league_key or key, False, prev.is_finished))
            key = prev.previous_league_key
        return seasons, complete, results

    def final_season(self, league_key: str, finished: bool, refresh: bool = False
                     ) -> tuple[list[Standing], CacheResult, list[TeamStats], CacheResult]:
        """Final standings and whole-season stats (playoff weeks included) for a league."""
        ttl = None if finished else CURRENT_TTL
        standings = self._fetch(f"league/{league_key}/standings", parse_standings, ttl, refresh)
        stats = self._fetch(f"league/{league_key}/teams/stats", parse_team_stats, ttl, refresh)
        return standings.data, standings, stats.data, stats

    def _league_or_denied(self, key: str) -> Callable[[], LeagueInfo | None]:
        """Fetch a previous league; None means this account can't read it (end of history).

        Yahoo also answers 403 for a bad credential, so a 403 only counts as "no access" if the
        current league loads fine in the same moment (an uncached call; a cached current league
        proves nothing). Otherwise it's an outage: re-raise, and the cache serves the old entry."""
        def fetch() -> LeagueInfo | None:
            try:
                return parse_league(self._http.get_json(f"league/{key}"))
            except YahooAccessDenied as denied:
                try:
                    self._http.get_json(self._league_path)
                except YahooUnavailable:
                    raise denied from None
                return None
        return fetch

    def _fetch(self, path: str, parse: Callable[[dict], object], ttl: float | None, refresh: bool,
               key: str | None = None) -> CacheResult:
        return self._cache.get_or_fetch(key or path, lambda: parse(self._http.get_json(path)), ttl, refresh)
