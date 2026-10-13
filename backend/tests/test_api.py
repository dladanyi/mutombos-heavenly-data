import re

import pytest

from app import create_app
from app.cache import CacheResult
from app.errors import YahooUnavailable
from app.parsing import LeagueInfo, TeamStats

FETCHED_AT = 1_791_000_000.0  # 2026-10-03T04:00:00Z


def result(stale=False, throttled=False, final=False):
    return CacheResult(data=None, fetched_at=FETCHED_AT, stale=stale, refresh_throttled=throttled, final=final)


TEAMS = [
    TeamStats("k.1", "Alpha", {"12": "100", "5": ".500", "9004003": "50/100", "19": "10"}),
    TeamStats("k.2", "Beta", {"12": "90", "5": ".400", "9004003": "40/100", "19": "12"}),
]


class FakeClient:
    def __init__(self):
        self.league_info = LeagueInfo("Mutombo's Heavenly Block Party", current_week=7, start_week=1, end_week=21)
        self.league_result = result()
        self.stats_result = result()
        self.state = "current"
        self.error = None
        self.calls = []

    def _maybe_fail(self):
        if self.error:
            raise self.error

    def league(self, refresh=False):
        self.calls.append(("league", refresh))
        self._maybe_fail()
        return self.league_info, self.league_result

    def season_stats(self, refresh=False):
        self.calls.append(("season", refresh))
        self._maybe_fail()
        return TEAMS, self.stats_result

    def week_stats(self, week, current_week, refresh=False):
        self.calls.append(("week", week, current_week, refresh))
        self._maybe_fail()
        return TEAMS, self.stats_result, self.state


@pytest.fixture
def client():
    return FakeClient()


@pytest.fixture
def static_dir(tmp_path):
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    return tmp_path


@pytest.fixture
def http(client, static_dir):
    return create_app(client=client, static_dir=static_dir).test_client()


def headers(response):
    return response.headers.get("Cache-Control"), response.headers.get("Vercel-CDN-Cache-Control")


SHORT = ("public, max-age=60", "max-age=60")
NO_STORE = ("no-store", "no-store")


def test_healthz(http, client):
    response = http.get("/healthz")
    assert (response.status_code, response.get_data(as_text=True)) == (200, "ok")
    assert headers(response) == NO_STORE
    assert client.calls == []


def test_league_shape(http):
    response = http.get("/api/league")
    body = response.get_json()
    assert set(body) == {"name", "current_week", "start_week", "end_week", "categories"}
    assert (body["current_week"], body["start_week"], body["end_week"]) == (7, 1, 21)
    assert body["categories"][6] == {"key": "FG%", "higher_is_better": True, "detail_label": "FGM/FGA"}
    assert body["categories"][8] == {"key": "TO", "higher_is_better": False}
    assert headers(response) == SHORT


def test_season_rankings_shape(http):
    response = http.get("/api/rankings/season")
    body = response.get_json()
    assert (body["scope"], body["week"], body["stale"], body["refresh_throttled"]) == ("season", None, False, False)
    assert len(body["categories"]) == 9
    assert body["teams"][0]["name"] == "Alpha"
    assert body["teams"][0]["stats"]["FG%"] == {"value": 0.5, "rank": 1, "detail": "50/100"}
    assert headers(response) == SHORT


def test_current_week_resolves_number(http, client):
    response = http.get("/api/rankings/week/current")
    body = response.get_json()
    assert (body["scope"], body["week"]) == ("week", 7)
    assert ("week", 7, 7, False) in client.calls
    assert headers(response) == SHORT


def test_week_cache_headers_by_state(http, client):
    client.state = "settling"
    assert headers(http.get("/api/rankings/week/6")) == ("public, max-age=300", "max-age=3600")
    client.state = "final"
    assert headers(http.get("/api/rankings/week/3")) == ("public, max-age=86400", "max-age=31536000")


def test_stale_and_errors_not_cached(http, client):
    client.stats_result = result(stale=True)
    response = http.get("/api/rankings/season")
    assert response.get_json()["stale"] is True
    assert headers(response) == NO_STORE
    assert headers(http.get("/api/rankings/week/99")) == NO_STORE
    client.error = YahooUnavailable("down")
    assert headers(http.get("/api/league")) == NO_STORE


def test_refresh_passes_flag_and_no_store(http, client):
    response = http.get("/api/rankings/week/6?refresh=1")
    assert ("week", 6, 7, True) in client.calls
    assert headers(response) == NO_STORE
    http.get("/api/rankings/season?refresh=1")
    assert ("season", True) in client.calls


def test_refresh_throttled_flag(http, client):
    client.stats_result = result(throttled=True)
    assert http.get("/api/rankings/season?refresh=1").get_json()["refresh_throttled"] is True


@pytest.mark.parametrize("week", ["8", "0", "abc", "-1", "7.5"])
def test_out_of_range_week_404(http, week):
    response = http.get(f"/api/rankings/week/{week}")
    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}


def test_week_one_has_no_previous(http, client):
    client.league_info = LeagueInfo("L", current_week=1, start_week=1, end_week=21)
    assert http.get("/api/rankings/week/0").status_code == 404
    assert http.get("/api/rankings/week/current").get_json()["week"] == 1


def test_yahoo_unavailable_503_json(http, client):
    client.error = YahooUnavailable("Yahoo returned HTTP 403 for league/x")
    response = http.get("/api/rankings/season")
    assert response.status_code == 503
    assert response.get_json()["error"] == "yahoo_unavailable"


def test_stale_flag_propagates(http, client):
    client.league_result = result(stale=True)
    assert http.get("/api/rankings/week/current").get_json()["stale"] is True


def test_unexpected_error_500_json(http, client):
    client.error = RuntimeError("bug")
    response = http.get("/api/league")
    assert response.status_code == 500
    assert response.get_json() == {"error": "internal", "message": "Internal error"}


def test_unknown_api_path_404_json(http):
    response = http.get("/api/nope")
    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}


def test_spa_fallback_and_static_file(http):
    assert http.get("/").get_data(as_text=True) == "<html>app</html>"
    assert http.get("/some/page").get_data(as_text=True) == "<html>app</html>"
    assert http.get("/assets/app.js").get_data(as_text=True) == "console.log(1)"


def test_missing_frontend_build_404_json(client, tmp_path):
    response = create_app(client=client, static_dir=tmp_path / "missing").test_client().get("/")
    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}


def test_fetched_at_iso_utc(http):
    fetched_at = http.get("/api/rankings/season").get_json()["fetched_at"]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", fetched_at)
    assert fetched_at == "2026-10-03T04:00:00Z"
