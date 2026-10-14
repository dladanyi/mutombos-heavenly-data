"""JSON API routes, cache headers and error handling (spec §5.5)."""
import logging
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Flask, Response, current_app, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException, NotFound

from app.cache import CacheResult
from app.config import CATEGORIES
from app.errors import YahooUnavailable
from app.rankings import build_rankings

log = logging.getLogger(__name__)
api = Blueprint("api", __name__)

# (browser Cache-Control, Vercel-CDN-Cache-Control)
_HEADERS = {
    "short": ("public, max-age=60", "max-age=60"),
    "settling": ("public, max-age=300", "max-age=3600"),
    "final": ("public, max-age=86400", "max-age=31536000"),
    "none": ("no-store", "no-store"),
}
_STATE_HEADERS = {"current": "short", "settling": "settling", "final": "final"}
_ALIASES = ("current", "previous")


def _client():
    return current_app.config["YAHOO_CLIENT"]


def _refresh() -> bool:
    return request.args.get("refresh") == "1"


def _respond(body, kind: str, *results: CacheResult) -> Response:
    if _refresh() or any(r.stale for r in results):
        kind = "none"
    response = body if isinstance(body, Response) else jsonify(body)
    response.headers["Cache-Control"], response.headers["Vercel-CDN-Cache-Control"] = _HEADERS[kind]
    return response


def _categories() -> list[dict]:
    out = []
    for c in CATEGORIES:
        item = {"key": c.key, "higher_is_better": c.higher_is_better}
        if c.detail_label:
            item["detail_label"] = c.detail_label
        out.append(item)
    return out


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rankings_body(scope: str, week: int | None, teams, stats: CacheResult, *others: CacheResult) -> dict:
    return {
        "scope": scope,
        "week": week,
        "fetched_at": _iso(stats.fetched_at),
        "stale": stats.stale or any(o.stale for o in others),
        "refresh_throttled": stats.refresh_throttled,
        "categories": _categories(),
        "teams": build_rankings(teams),
    }


@api.get("/healthz")
def healthz():
    return _respond(Response("ok", mimetype="text/plain"), "none")


@api.get("/api/league")
def league():
    info, result = _client().league(refresh=_refresh())
    body = {"name": info.name, "current_week": info.current_week, "start_week": info.start_week,
            "end_week": info.end_week, "categories": _categories()}
    return _respond(body, "short", result)


@api.get("/api/rankings/season")
def season_rankings():
    teams, result = _client().season_stats(refresh=_refresh())
    return _respond(_rankings_body("season", None, teams, result), "short", result)


@api.get("/api/rankings/week/<week>")
def week_rankings(week: str):
    info, league_result = _client().league()
    if week == "current":
        number = info.current_week
    elif week == "previous" and info.current_week > info.start_week:
        number = info.current_week - 1
    elif week.isdecimal() and info.start_week <= int(week) <= info.current_week:
        number = int(week)
    else:
        raise NotFound()
    teams, result, state = _client().week_stats(number, info.current_week, refresh=_refresh())
    body = {**_rankings_body("week", number, teams, result, league_result), "state": state}
    # Long CDN caching only for data that was itself fetched as final (spec §5.2): an entry
    # fetched while settling may still be served after the week turns final.
    kind = _STATE_HEADERS[state] if state != "final" or result.final else "settling"
    # An alias names a different week after each rollover, so the CDN may only keep it briefly.
    # (The server-side cache still holds a final week forever.)
    if week in _ALIASES:
        kind = "short"
    return _respond(body, kind, result, league_result)


@api.get("/", defaults={"path": ""})
@api.get("/<path:path>")
def frontend(path: str):
    if path == "api" or path.startswith("api/"):
        raise NotFound()
    static_dir: Path = current_app.config["STATIC_DIR"]
    if path and (static_dir / path).is_file():
        return send_from_directory(static_dir, path)
    if (static_dir / "index.html").is_file():
        return send_from_directory(static_dir, "index.html")
    raise NotFound()


def _error(status: int, body: dict) -> Response:
    response = jsonify(body)
    response.status_code = status
    response.headers["Cache-Control"], response.headers["Vercel-CDN-Cache-Control"] = _HEADERS["none"]
    return response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(YahooUnavailable)
    def yahoo_unavailable(exc: YahooUnavailable):
        log.warning("Yahoo unavailable", extra={"path": request.path, "error": str(exc)})
        return _error(503, {"error": "yahoo_unavailable",
                            "message": "Yahoo Fantasy is unavailable right now. Try again shortly."})

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        code = "not_found" if exc.code == 404 else (exc.name or "error").lower().replace(" ", "_")
        return _error(exc.code or 500, {"error": code})

    @app.errorhandler(Exception)
    def unexpected(exc: Exception):
        log.exception("Unhandled error", extra={"path": request.path})
        return _error(500, {"error": "internal", "message": "Internal error"})
