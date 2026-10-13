import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.cache import Cache
from app.errors import YahooUnavailable
from app.yahoo_client import YahooClient, pacific_today

FIXTURES = Path(__file__).parent / "fixtures"
LEAGUE = "league/nba.l.46425"
WEEK3_END = date(2026, 11, 9)  # synthetic calendar: week 3 = 2026-11-03..2026-11-09


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


class FakeHttp:
    def __init__(self):
        self.calls = Counter()
        self.failing = set()
        self.overrides = {}

    def get_json(self, path):
        self.calls[path] += 1
        if path in self.failing:
            raise YahooUnavailable(f"{path} down")
        if path in self.overrides:
            return self.overrides[path]
        if path == LEAGUE:
            return fixture("league.json")
        if path == "game/nba/game_weeks":
            return fixture("game_weeks.json")
        if path == f"{LEAGUE}/teams/stats":
            return fixture("season_stats.json")
        if path.startswith(f"{LEAGUE}/teams/stats;type=week;week="):
            return fixture("week_stats.json")
        raise AssertionError(f"unexpected path {path}")


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


class Today:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


@pytest.fixture
def setup():
    http, clock, today = FakeHttp(), Clock(), Today(date(2026, 11, 12))
    client = YahooClient(http, "46425", Cache(clock=clock), today=today)
    return client, http, clock, today


def week_path(n):
    return f"{LEAGUE}/teams/stats;type=week;week={n}"


def test_week_state_current(setup):
    client, *_ = setup
    assert client.week_state(7, current_week=7) == "current"
    assert client.week_state(8, current_week=7) == "current"


def test_week_state_boundary(setup):
    client, _, _, today = setup
    today.value = WEEK3_END.replace(day=12)
    assert client.week_state(3, current_week=7) == "settling"
    today.value = WEEK3_END.replace(day=13)
    assert client.week_state(3, current_week=7) == "final"
    today.value = WEEK3_END
    assert client.week_state(3, current_week=7) == "settling"


def test_pacific_today_uses_la_date():
    assert pacific_today(datetime(2026, 11, 13, 7, 30, tzinfo=timezone.utc)) == date(2026, 11, 12)
    assert pacific_today(datetime(2026, 11, 13, 8, 30, tzinfo=timezone.utc)) == date(2026, 11, 13)
    assert isinstance(pacific_today(), date)


def test_calendar_failure_means_not_final(setup):
    client, http, clock, today = setup
    today.value = date(2027, 1, 1)
    http.failing.add("game/nba/game_weeks")
    assert client.week_state(3, current_week=7) == "settling"
    http.failing.clear()
    assert client.week_state(3, current_week=7) == "settling"  # 30 s failure cooldown, no retry yet
    clock.now += 31
    assert client.week_state(3, current_week=7) == "final"
    assert http.calls["game/nba/game_weeks"] == 2


def test_week_missing_from_calendar_is_settling(setup):
    client, *_ = setup
    assert client.week_state(99, current_week=120) == "settling"


def test_calendar_fetched_once(setup):
    client, http, clock, _ = setup
    for week in range(1, 7):
        client.week_state(week, current_week=7)
        clock.now += 10 ** 7
    assert http.calls["game/nba/game_weeks"] == 1


def test_final_week_cached_forever(setup):
    client, http, clock, _ = setup
    _, first, state = client.week_stats(2, current_week=7)  # week 2 ended 2026-11-02
    clock.now += 365 * 86400
    teams, second, _ = client.week_stats(2, current_week=7, refresh=True)
    assert state == "final"
    assert http.calls[week_path(2)] == 1
    assert first.final and second.final
    assert len(teams) == 12


def test_settling_week_ttl_one_hour(setup):
    client, http, clock, today = setup
    today.value = date(2026, 11, 10)
    assert client.week_stats(3, current_week=4)[2] == "settling"
    clock.now += 3599
    client.week_stats(3, current_week=4)
    assert http.calls[week_path(3)] == 1
    clock.now += 2
    client.week_stats(3, current_week=4)
    assert http.calls[week_path(3)] == 2


def test_current_week_ttl_five_minutes(setup):
    client, http, clock, _ = setup
    client.week_stats(7, current_week=7)
    clock.now += 301
    client.week_stats(7, current_week=7)
    assert http.calls[week_path(7)] == 2


def test_week_fetched_while_settling_becomes_final_later(setup):
    client, http, clock, today = setup
    today.value = date(2026, 11, 12)
    _, result, state = client.week_stats(3, current_week=4)
    assert (state, result.final) == ("settling", False)
    today.value = date(2026, 11, 13)
    clock.now += 3601
    _, result, state = client.week_stats(3, current_week=4)
    assert (state, result.final) == ("final", True)
    clock.now += 10 ** 8
    client.week_stats(3, current_week=4)
    assert http.calls[week_path(3)] == 2


def test_league_and_season_ttl_five_minutes(setup):
    client, http, clock, _ = setup
    league, _ = client.league()
    client.season_stats()
    clock.now += 299
    client.league()
    client.season_stats()
    assert (http.calls[LEAGUE], http.calls[f"{LEAGUE}/teams/stats"]) == (1, 1)
    clock.now += 2
    client.league()
    client.season_stats()
    assert (http.calls[LEAGUE], http.calls[f"{LEAGUE}/teams/stats"]) == (2, 2)
    assert league.current_week == 7


def test_refresh_passed_through(setup):
    client, http, clock, _ = setup
    client.season_stats()
    clock.now += 31
    client.season_stats(refresh=True)
    assert http.calls[f"{LEAGUE}/teams/stats"] == 2


def test_format_error_serves_stale(setup):
    client, http, clock, _ = setup
    client.season_stats()
    clock.now += 301
    http.overrides[f"{LEAGUE}/teams/stats"] = {}
    teams, result = client.season_stats()
    assert result.stale is True
    assert len(teams) == 12


def test_unavailable_without_cache_raises(setup):
    client, http, *_ = setup
    http.failing.add(LEAGUE)
    with pytest.raises(YahooUnavailable):
        client.league()
