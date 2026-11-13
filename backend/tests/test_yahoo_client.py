import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.cache import Cache
from app.errors import YahooAccessDenied, YahooUnavailable
from app.parsing import parse_game_weeks
from app.yahoo_client import YahooClient, pacific_today

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


# Read from the fixtures so a re-capture doesn't need hand edits
# (2026-27: league 46425, 10 teams, week 3 ends 2026-11-08).
LEAGUE_META = fixture("league.json")["fantasy_content"]["league"][0]
LEAGUE_ID = str(LEAGUE_META["league_id"])
LEAGUE = f"league/nba.l.{LEAGUE_ID}"
NUM_TEAMS = int(LEAGUE_META["num_teams"])
WEEK3_END = parse_game_weeks(fixture("game_weeks.json"))[3].end
PREV = "league/" + fixture("league.json")["fantasy_content"]["league"][0]["renew"].replace("_", ".l.")
OLDEST = "league/" + fixture("prev_league.json")["fantasy_content"]["league"][0]["renew"].replace("_", ".l.")


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
        if path.startswith(f"{LEAGUE}/scoreboard;week="):
            return fixture("scoreboard.json")
        if path == PREV:
            return fixture("prev_league.json")
        if path == f"{PREV}/standings":
            return fixture("prev_standings.json")
        if path == f"{PREV}/teams/stats":
            return fixture("prev_season_stats.json")
        if path == OLDEST:
            raise YahooAccessDenied(f"Yahoo returned HTTP 403 for {path}")
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
    # Default: 4 days after week 3 ends, so weeks 1-3 are final.
    http, clock, today = FakeHttp(), Clock(), Today(WEEK3_END + timedelta(days=4))
    client = YahooClient(http, LEAGUE_ID, Cache(clock=clock), today=today)
    return client, http, clock, today


def week_path(n):
    return f"{LEAGUE}/teams/stats;type=week;week={n}"


def test_week_state_current(setup):
    client, *_ = setup
    assert client.week_state(7, current_week=7) == "current"
    assert client.week_state(8, current_week=7) == "current"


def test_current_week_past_its_end_follows_calendar(setup):
    """After the season, Yahoo leaves current_week on the last week; it must still go final."""
    client, _, _, today = setup
    today.value = WEEK3_END
    assert client.week_state(3, current_week=3) == "current"
    today.value = WEEK3_END + timedelta(days=1)
    assert client.week_state(3, current_week=3) == "settling"
    today.value = WEEK3_END + timedelta(days=4)
    assert client.week_state(3, current_week=3) == "final"


def test_current_week_calendar_failure_stays_current(setup):
    client, http, _, today = setup
    today.value = date(2027, 1, 1)
    http.failing.add("game/nba/game_weeks")
    assert client.week_state(3, current_week=3) == "current"


def test_week_state_boundary(setup):
    client, _, _, today = setup
    today.value = WEEK3_END + timedelta(days=3)
    assert client.week_state(3, current_week=7) == "settling"
    today.value = WEEK3_END + timedelta(days=4)
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
    _, first, state = client.week_stats(2, current_week=7)  # week 2 is final by the default date
    clock.now += 365 * 86400
    teams, second, _ = client.week_stats(2, current_week=7, refresh=True)
    assert state == "final"
    assert http.calls[week_path(2)] == 1
    assert first.final and second.final
    assert len(teams) == NUM_TEAMS


def test_settling_week_ttl_one_hour(setup):
    client, http, clock, today = setup
    today.value = WEEK3_END + timedelta(days=1)
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
    today.value = WEEK3_END + timedelta(days=3)
    _, result, state = client.week_stats(3, current_week=4)
    assert (state, result.final) == ("settling", False)
    today.value = WEEK3_END + timedelta(days=4)
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
    assert league.current_week == int(LEAGUE_META["current_week"])


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
    assert len(teams) == NUM_TEAMS


def test_unavailable_without_cache_raises(setup):
    client, http, *_ = setup
    http.failing.add(LEAGUE)
    with pytest.raises(YahooUnavailable):
        client.league()


def scoreboard_path(n):
    return f"{LEAGUE}/scoreboard;week={n}"


def test_week_results_final_cached_forever(setup):
    client, http, clock, _ = setup
    results, first = client.week_results(2, "final")
    clock.now += 365 * 86400
    client.week_results(2, "final", refresh=True)
    assert http.calls[scoreboard_path(2)] == 1
    assert first.final and len(results) == NUM_TEAMS


def test_week_results_settling_ttl_one_hour(setup):
    client, http, clock, today = setup
    today.value = WEEK3_END + timedelta(days=1)
    _, result = client.week_results(3, "settling")
    assert not result.final
    clock.now += 3601
    client.week_results(3, "settling")
    assert http.calls[scoreboard_path(3)] == 2


def test_week_results_refresh_passed_through(setup):
    client, http, clock, today = setup
    today.value = WEEK3_END + timedelta(days=1)
    client.week_results(3, "settling")
    clock.now += 31
    client.week_results(3, "settling", refresh=True)
    assert http.calls[scoreboard_path(3)] == 2


def test_week_results_does_not_recompute_state(setup):
    client, http, *_ = setup
    client.week_results(3, "settling")
    assert http.calls["game/nba/game_weeks"] == 0



def test_seasons_walks_renew_chain(setup):
    client, http, *_ = setup
    seasons, complete, results = client.seasons()
    assert [(s.season, s.current, s.finished) for s in seasons] == [(2026, True, False), (2025, False, True)]
    assert seasons[1].league_key == PREV.removeprefix("league/")
    assert complete is True and results
    assert http.calls[OLDEST] == 1


def test_seasons_access_denied_stop_cached_one_day(setup):
    client, http, clock, _ = setup
    client.seasons()
    clock.now += 86399
    client.seasons()
    assert http.calls[OLDEST] == 1
    clock.now += 2
    client.seasons()
    assert http.calls[OLDEST] == 2


def test_seasons_outage_marks_incomplete_and_is_not_cached(setup):
    client, http, clock, _ = setup
    http.failing.add(PREV)
    seasons, complete, _ = client.seasons()
    assert [s.season for s in seasons] == [2026] and complete is False
    http.failing.discard(PREV)
    clock.now += 31
    seasons, complete, _ = client.seasons()
    assert [s.season for s in seasons] == [2026, 2025] and complete is True


def test_seasons_loop_guard(setup):
    client, http, *_ = setup
    looping = fixture("prev_league.json")
    looping["fantasy_content"]["league"][0]["renew"] = PREV.removeprefix("league/").replace(".l.", "_")
    http.overrides[PREV] = looping
    seasons, complete, _ = client.seasons()
    assert len(seasons) == 20


def test_final_season_finished_cached_forever(setup):
    client, http, clock, _ = setup
    key = PREV.removeprefix("league/")
    standings, std_result, teams, stats_result = client.final_season(key, finished=True)
    clock.now += 365 * 86400
    client.final_season(key, finished=True, refresh=True)
    assert http.calls[f"{PREV}/standings"] == 1 and http.calls[f"{PREV}/teams/stats"] == 1
    assert std_result.final and stats_result.final
    assert len(standings) == len(teams) == NUM_TEAMS and standings[0].rank == 1


def test_final_season_unfinished_uses_current_ttl(setup):
    client, http, clock, _ = setup
    key = PREV.removeprefix("league/")
    client.final_season(key, finished=False)
    clock.now += 301
    client.final_season(key, finished=False)
    assert http.calls[f"{PREV}/standings"] == 2
