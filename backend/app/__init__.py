from pathlib import Path

from flask import Flask

DEFAULT_STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(*, settings=None, client=None, static_dir: Path | None = None) -> Flask:
    """Build the Flask app. With no arguments, reads env vars and talks to Yahoo."""
    from app.api import api, register_error_handlers

    if client is None:
        from app.cache import Cache
        from app.config import load_settings
        from app.logging_setup import configure_logging
        from app.yahoo_client import YahooClient
        from app.yahoo_http import YahooHttp

        configure_logging()
        settings = settings or load_settings()
        http = YahooHttp(settings.consumer_key, settings.consumer_secret, settings.refresh_token)
        client = YahooClient(http, settings.league_id, Cache())

    app = Flask(__name__, static_folder=None)
    app.config["YAHOO_CLIENT"] = client
    app.config["STATIC_DIR"] = Path(static_dir) if static_dir else DEFAULT_STATIC_DIR
    app.json.sort_keys = False
    app.register_blueprint(api)
    register_error_handlers(app)
    return app
