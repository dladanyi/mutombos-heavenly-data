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

log = logging.getLogger(__name__)


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

            log.warning("Yahoo request failed", extra={"path": path, "status": status, "attempt": attempt})
            if attempt == 1 and status == 401:
                self._token(force=True)
                continue
            if attempt == 1 and status >= 500 and status != _RATE_LIMITED:
                continue
            raise YahooUnavailable(f"Yahoo returned HTTP {status} for {path}")
        raise AssertionError("unreachable")

    def _token(self, force: bool) -> str:
        with self._lock:
            if force or self._access_token is None or self._clock() >= self._expires_at - _EXPIRY_MARGIN:
                self._renew()
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
            log.error("Yahoo token refresh rejected", extra={"status": response.status_code})
            raise YahooUnavailable(f"Yahoo token refresh returned HTTP {response.status_code}")
        try:
            body = response.json()
            access_token = body["access_token"]
        except (ValueError, KeyError) as exc:
            raise YahooUnavailable("Yahoo token refresh returned an unexpected body") from exc

        self._access_token = access_token
        self._expires_at = self._clock() + float(body.get("expires_in", 3600))
        if body.get("refresh_token"):
            self._refresh_token = body["refresh_token"]
