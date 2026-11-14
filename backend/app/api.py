"""JSON API routes, cache headers and error handling (spec §5.5)."""
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Flask, Response, current_app, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException, NotFound

from app.cache import CacheResult
from app.config import CATEGORIES
from app.errors import YahooUnavailable
from app.parsing import MatchupResult, Standing
from app.rankings import build_rankings
from app.stars import LEVELS, build_star_power

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
    others: list[CacheResult] = []
    records: dict[str, dict] | None = None
    try:
        standings, standings_result = _client().standings(refresh=_refresh())
        others.append(standings_result)
        records = {s.team_key: {"wins": s.wins, "losses": s.losses, "ties": s.ties} for s in standings}
    except YahooUnavailable as exc:  # includes YahooFormatError
        # The rankings are still useful without records; just don't let anything cache this.
        log.warning("Season standings unavailable", extra={"error": str(exc)})
    body = _rankings_body("season", None, teams, result, *others)
    for row in body["teams"]:
        row["record"] = (records or {}).get(row["team_key"])
    return _respond(body, "short" if records is not None else "none", result, *others)


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
    others = [league_result]
    results_ok = True
    results: dict[str, MatchupResult] = {}
    # Head-to-head results: final once the week is over, live (category leaders so far) before.
    try:
        results, results_result = _client().week_results(number, state, refresh=_refresh())
        others.append(results_result)
    except YahooUnavailable as exc:  # includes YahooFormatError (a subclass)
        # The rankings are still useful without results; just don't let anything cache this.
        log.warning("Week results unavailable", extra={"week": number, "error": str(exc)})
        results_ok = False
    body = {**_rankings_body("week", number, teams, result, *others), "state": state}
    for row in body["teams"]:
        row["result"] = _result_json(results.get(row["team_key"]))
    # Long CDN caching only for data that was itself fetched as final (spec §5.2): an entry
    # fetched while settling may still be served after the week turns final.
    all_final = result.final and all(o.final for o in others[1:])
    kind = _STATE_HEADERS[state] if state != "final" or all_final else "settling"
    # An alias names a different week after each rollover, so the CDN may only keep it briefly.
    # (The server-side cache still holds a final week forever.)
    if week in _ALIASES:
        kind = "short"
    if not results_ok:
        kind = "none"
    return _respond(body, kind, result, *others)


def _result_json(r: MatchupResult | None) -> dict | None:
    if r is None:
        return None
    return {"outcome": r.outcome, "wins": r.wins, "losses": r.losses, "ties": r.ties,
            "opponent": {"team_key": r.opponent_key, "name": r.opponent_name}}


@api.get("/api/stars")
def stars():
    players, players_result = _client().top_players(refresh=_refresh())
    teams, teams_result = _client().season_stats()  # the league's team list (names, keys)
    body = {
        "fetched_at": _iso(players_result.fetched_at),
        "stale": players_result.stale or teams_result.stale,
        "refresh_throttled": players_result.refresh_throttled,
        "levels": list(LEVELS),
        **build_star_power(players, teams),
    }
    return _respond(body, "settling", players_result, teams_result)  # 5 min browser, 1 h CDN


@api.get("/api/stars/<season>")
def past_stars(season: str):
    """Star Power for a finished season: final full-season ranks and end-of-season rosters."""
    ref, walk_results = _finished_season(season)
    players, players_result = _client().season_top_players(ref.league_key, ref.finished, refresh=_refresh())
    teams, teams_result = _client().season_teams(ref.league_key, ref.finished, refresh=_refresh())
    results = (players_result, teams_result, *walk_results)
    body = {
        "season": ref.season,
        "league_key": ref.league_key,
        "fetched_at": _iso(players_result.fetched_at),
        "stale": any(r.stale for r in results),
        "refresh_throttled": players_result.refresh_throttled,
        "levels": list(LEVELS),
        **build_star_power(players, teams),
    }
    kind = "final" if players_result.final and teams_result.final else "settling"
    return _respond(body, kind, *results)


@api.get("/api/seasons")
def seasons():
    refs, complete, results = _client().seasons(refresh=_refresh())
    body = {"seasons": [{"season": s.season, "league_key": s.league_key, "current": s.current,
                         "finished": s.finished} for s in refs], "complete": complete}
    return _respond(body, "short" if complete else "none", *results)


def _finished_season(season: str):
    """The SeasonRef for a finished season (any past season, or the current one once Yahoo marks
    it finished) plus the renew-walk results up to it. 404 for anything else."""
    if not re.fullmatch(r"[0-9]{4}", season):  # ASCII only: isdecimal() lets in 5000-digit and non-ASCII digits
        raise NotFound()
    refs, complete, walk_results = _client().seasons(refresh=_refresh())
    index = next((i for i, s in enumerate(refs) if s.season == int(season)), None)
    if index is None:
        if not complete:  # an outage cut the walk short, so "not found" isn't known
            raise YahooUnavailable("season list incomplete")
        raise NotFound()
    ref = refs[index]
    if ref.current and not ref.finished:
        raise NotFound()  # the in-progress season is served by the current-season endpoints
    # Walk results line up with refs; only the leagues up to the requested one matter here.
    return ref, walk_results[:index + 1]


@api.get("/api/seasons/<season>")
def final_season(season: str):
    """A finished season: any past season, or the current one once Yahoo marks it finished."""
    ref, walk_results = _finished_season(season)
    standings, standings_result, teams, stats_result = _client().final_season(
        ref.league_key, ref.finished, refresh=_refresh())
    body = {
        "season": ref.season,
        "league_key": ref.league_key,
        "fetched_at": _iso(standings_result.fetched_at),
        "stale": any(r.stale for r in (standings_result, stats_result, *walk_results)),
        "categories": _categories(),
        "standings": [_standing_json(s) for s in sorted(standings, key=lambda s: (s.rank is None, s.rank or 0))],
        "teams": build_rankings(teams),
    }
    kind = "final" if ref.finished and standings_result.final and stats_result.final else "short"
    return _respond(body, kind, standings_result, stats_result, *walk_results)


def _standing_json(s: Standing) -> dict:
    return {"rank": s.rank, "team_key": s.team_key, "name": s.name, "wins": s.wins, "losses": s.losses,
            "ties": s.ties, "percentage": s.percentage, "playoff_seed": s.playoff_seed}


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
