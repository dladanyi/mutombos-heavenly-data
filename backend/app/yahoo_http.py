"""Minimal Yahoo Fantasy API client: OAuth2 refresh-token flow plus JSON GETs.

Never prompts for input and never writes tokens anywhere but memory.
"""
import logging
import threading
import time
from collections.abc import Callable

import requests

from app.errors import YahooUnavailable

TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2/"

# Renew the access token this many seconds before Yahoo says it expires.
_EXPIRY_MARGIN = 60
_RATE_LIMITED = 999
# After a failed token refresh, fail fast for this long instead of re-posting on every request.
_RENEW_COOLDOWN = 30.0
# Longest Yahoo error message kept in a log line.
_MAX_ERROR_CHARS = 300

log = logging.getLogger(__name__)


def _yahoo_error(response) -> str:
    """Yahoo's own explanation of a failed request, for logs. The API returns
    {"error": {"description": ...}}; the token endpoint {"error": ..., "error_description": ...}."""
    try:
        body = response.json()
    except ValueError:
        body = None
    message = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("description")
        elif isinstance(error, str):
            message = f"{error}: {body['error_description']}" if body.get("error_description") else error
    if not isinstance(message, str):
        message = response.text or ""
    return message.strip()[:_MAX_ERROR_CHARS]


class YahooHttp:
    def __init__(self, consumer_key: str, consumer_secret: str, refresh_token: str, *,
                 session: requests.Session | None = None,
                 clock: Callable[[], float] = time.time,
                 timeout: float = 10.0):
        self._auth = (consumer_key, consumer_secret)
        self._refresh_token = refresh_token
        self._session = session or requests.Session()
        self._clock = clock
        self._timeout = timeout
        self._lock = threading.Lock()
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._renew_failed_until = 0.0

    def get_json(self, path: str) -> dict:
        url = API_BASE + path
        for attempt in (1, 2):
            token = self._token(force=False)
            try:
                response = self._session.get(
                    url, params={"format": "json"},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self._timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                log.warning("Yahoo request failed", extra={"path": path, "error": type(exc).__name__,
                                                           "attempt": attempt})
                if attempt == 2:
                    raise YahooUnavailable(f"Yahoo request for {path} failed: {type(exc).__name__}") from exc
                continue

            status = response.status_code
            if 200 <= status < 300:
                try:
                    return response.json()
                except ValueError as exc:
                    raise YahooUnavailable(f"Yahoo returned non-JSON for {path}") from exc

            log.warning("Yahoo request failed", extra={"path": path, "status": status, "attempt": attempt,
                                                       "yahoo_error": _yahoo_error(response)})
            if attempt == 1 and status == 401:
                self._token(force=True, rejected=token)
                continue
            if attempt == 1 and status >= 500 and status != _RATE_LIMITED:
                continue
            raise YahooUnavailable(f"Yahoo returned HTTP {status} for {path}")
        raise AssertionError("unreachable")

    def _token(self, force: bool, rejected: str | None = None) -> str:
        """Return a valid access token. A forced renew is skipped if another request already
        replaced the `rejected` token, so concurrent 401s renew it only once."""
        with self._lock:
            force = force and (rejected is None or rejected == self._access_token)
            if force or self._access_token is None or self._clock() >= self._expires_at - _EXPIRY_MARGIN:
                if self._clock() < self._renew_failed_until:
                    raise YahooUnavailable("Yahoo token refresh failed recently; retrying after cooldown")
                try:
                    self._renew()
                except YahooUnavailable:
                    self._renew_failed_until = self._clock() + _RENEW_COOLDOWN
                    raise
            return self._access_token

    def _renew(self) -> None:
        try:
            response = self._session.post(
                TOKEN_URL, auth=self._auth,
                data={"grant_type": "refresh_token", "refresh_token": self._refresh_token,
                      "redirect_uri": "oob"},
                timeout=self._timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise YahooUnavailable(f"Yahoo token refresh failed: {type(exc).__name__}") from exc

        if response.status_code != 200:
            log.error("Yahoo token refresh rejected", extra={"status": response.status_code,
                                                             "yahoo_error": _yahoo_error(response)})
            raise YahooUnavailable(f"Yahoo token refresh returned HTTP {response.status_code}")
        try:
            body = response.json()
            access_token = body["access_token"]
            expires_in = float(body.get("expires_in", 3600))
            new_refresh_token = body.get("refresh_token")
            if not isinstance(access_token, str) or not access_token:
                raise ValueError("access_token missing")
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise YahooUnavailable("Yahoo token refresh returned an unexpected body") from exc

        self._access_token = access_token
        self._expires_at = self._clock() + expires_in
        if new_refresh_token:
            self._refresh_token = new_refresh_token
