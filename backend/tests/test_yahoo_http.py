import pytest
import requests

from app.errors import YahooUnavailable
from app.yahoo_http import API_BASE, TOKEN_URL, YahooHttp


class FakeResponse:
    def __init__(self, status, body=None, text=None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else ""

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


class FakeSession:
    """Returns queued responses (or raises queued exceptions) and records calls."""

    def __init__(self, posts=(), gets=()):
        self.posts = list(posts)
        self.gets = list(gets)
        self.post_calls = []
        self.get_calls = []

    def _next(self, queue):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item()
        return item

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self._next(self.posts)

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self._next(self.gets)


def token(access="t1", refresh=None, expires_in=3600):
    body = {"access_token": access, "token_type": "bearer", "expires_in": expires_in}
    if refresh:
        body["refresh_token"] = refresh
    return FakeResponse(200, body)


class Clock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


def make(session, clock=None):
    return YahooHttp("key", "secret", "r-secret", session=session, clock=clock or Clock())


def test_first_call_fetches_token_then_data():
    session = FakeSession(posts=[token()], gets=[FakeResponse(200, {"ok": 1})])
    assert make(session).get_json("league/nba.l.1") == {"ok": 1}

    (post_url, post_kwargs), = session.post_calls
    assert post_url == TOKEN_URL
    assert post_kwargs["auth"] == ("key", "secret")
    assert post_kwargs["data"] == {"grant_type": "refresh_token", "refresh_token": "r-secret",
                                   "redirect_uri": "oob"}
    assert post_kwargs["timeout"] == 10.0

    (get_url, get_kwargs), = session.get_calls
    assert get_url == API_BASE + "league/nba.l.1"
    assert get_kwargs["params"] == {"format": "json"}
    assert get_kwargs["headers"]["Authorization"] == "Bearer t1"
    assert get_kwargs["timeout"] == 10.0


def test_token_reused_until_60s_before_expiry():
    clock = Clock()
    session = FakeSession(posts=[token("t1"), token("t2")],
                          gets=[FakeResponse(200, {})] * 3)
    http = make(session, clock)
    http.get_json("a")
    clock.now = 3539
    http.get_json("b")
    assert len(session.post_calls) == 1
    clock.now = 3541
    http.get_json("c")
    assert len(session.post_calls) == 2
    assert session.get_calls[-1][1]["headers"]["Authorization"] == "Bearer t2"


def test_new_refresh_token_is_used_next_time():
    clock = Clock()
    session = FakeSession(posts=[token("t1", refresh="r-new"), token("t2")],
                          gets=[FakeResponse(200, {})] * 2)
    http = make(session, clock)
    http.get_json("a")
    clock.now = 4000
    http.get_json("b")
    assert session.post_calls[1][1]["data"]["refresh_token"] == "r-new"


def test_401_renews_token_and_retries_once():
    session = FakeSession(posts=[token("t1"), token("t2")],
                          gets=[FakeResponse(401, {}), FakeResponse(200, {"ok": 1})])
    assert make(session).get_json("a") == {"ok": 1}
    assert len(session.post_calls) == 2
    assert len(session.get_calls) == 2
    assert session.get_calls[1][1]["headers"]["Authorization"] == "Bearer t2"


def test_repeated_401_raises():
    session = FakeSession(posts=[token("t1"), token("t2")],
                          gets=[FakeResponse(401, {}), FakeResponse(401, {})])
    with pytest.raises(YahooUnavailable, match="401"):
        make(session).get_json("a")
    assert len(session.get_calls) == 2


def test_retry_once_on_timeout():
    session = FakeSession(posts=[token()],
                          gets=[requests.Timeout("slow"), FakeResponse(200, {"ok": 1})])
    assert make(session).get_json("a") == {"ok": 1}
    assert len(session.get_calls) == 2


def test_retry_once_on_connection_error_then_raise():
    session = FakeSession(posts=[token()],
                          gets=[requests.ConnectionError("x"), requests.ConnectionError("y")])
    with pytest.raises(YahooUnavailable):
        make(session).get_json("a")
    assert len(session.get_calls) == 2


def test_retry_once_on_500_then_raise():
    session = FakeSession(posts=[token()], gets=[FakeResponse(500, {}), FakeResponse(503, {})])
    with pytest.raises(YahooUnavailable, match="503"):
        make(session).get_json("a")
    assert len(session.get_calls) == 2


def test_999_not_retried():
    session = FakeSession(posts=[token()], gets=[FakeResponse(999, None)])
    with pytest.raises(YahooUnavailable, match="999"):
        make(session).get_json("a")
    assert len(session.get_calls) == 1


def test_404_raises_without_retry():
    session = FakeSession(posts=[token()], gets=[FakeResponse(404, {})])
    with pytest.raises(YahooUnavailable, match="404"):
        make(session).get_json("league/x")
    assert len(session.get_calls) == 1


def test_invalid_json_raises_unavailable():
    session = FakeSession(posts=[token()], gets=[FakeResponse(200, None, text="<html>")])
    with pytest.raises(YahooUnavailable):
        make(session).get_json("a")


def test_token_refresh_failure_raises_unavailable():
    session = FakeSession(posts=[FakeResponse(400, {"error": "invalid_grant"})])
    with pytest.raises(YahooUnavailable) as exc:
        make(session).get_json("a")
    assert session.get_calls == []
    assert "r-secret" not in str(exc.value)


def test_token_endpoint_timeout_raises_unavailable():
    session = FakeSession(posts=[requests.Timeout("slow")])
    with pytest.raises(YahooUnavailable):
        make(session).get_json("a")


def test_failed_token_refresh_not_retried_for_30s():
    clock = Clock()
    session = FakeSession(posts=[FakeResponse(400, {"error": "invalid_grant"}), token()],
                          gets=[FakeResponse(200, {"ok": 1})])
    http = make(session, clock)
    for _ in range(3):
        with pytest.raises(YahooUnavailable):
            http.get_json("a")
    assert len(session.post_calls) == 1
    clock.now += 31
    assert http.get_json("a") == {"ok": 1}
    assert len(session.post_calls) == 2


def test_401_after_another_request_renewed_reuses_new_token():
    """Concurrent 401s for the same rejected token renew it once, not once per request."""
    session = FakeSession(posts=[token("t1"), token("t2")])
    http = make(session)

    def first_response():
        # While this request is in flight, another request gets a 401 and renews the token.
        session.gets[:0] = [FakeResponse(401, {}), FakeResponse(200, {"other": 1})]
        assert http.get_json("other") == {"other": 1}
        return FakeResponse(401, {})

    session.gets = [first_response, FakeResponse(200, {"ok": 1})]
    assert http.get_json("league/nba.l.1") == {"ok": 1}
    assert len(session.post_calls) == 2
    assert session.get_calls[-1][1]["headers"]["Authorization"] == "Bearer t2"


@pytest.mark.parametrize("body", [
    {"access_token": "t1", "expires_in": None},
    {"access_token": "t1", "expires_in": "soon"},
    ["not", "a", "dict"],
    {"access_token": None},
])
def test_malformed_token_body_is_unavailable_and_cools_down(body):
    session = FakeSession(posts=[FakeResponse(200, body)])
    http = make(session)
    with pytest.raises(YahooUnavailable, match="unexpected body"):
        http.get_json("league/nba.l.1")
    with pytest.raises(YahooUnavailable, match="cooldown"):
        http.get_json("league/nba.l.1")
    assert len(session.post_calls) == 1
    assert session.get_calls == []
