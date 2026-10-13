import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Category:
    key: str
    stat_id: str
    higher_is_better: bool
    detail_stat_id: str | None = None
    detail_label: str | None = None


# Ranked categories, in display order.
CATEGORIES: tuple[Category, ...] = (
    Category("PTS", "12", True),
    Category("REB", "15", True),
    Category("AST", "16", True),
    Category("ST", "17", True),
    Category("BLK", "18", True),
    Category("3PTM", "10", True),
    Category("FG%", "5", True, detail_stat_id="9004003", detail_label="FGM/FGA"),
    Category("FT%", "8", True, detail_stat_id="9007006", detail_label="FTM/FTA"),
    Category("TO", "19", False),
)


@dataclass(frozen=True)
class Settings:
    consumer_key: str
    consumer_secret: str
    refresh_token: str
    league_id: str
    port: int


_REQUIRED = ("YAHOO_CONSUMER_KEY", "YAHOO_CONSUMER_SECRET", "YAHOO_REFRESH_TOKEN", "YAHOO_LEAGUE_ID")


def load_settings(env: Mapping[str, str] = os.environ) -> Settings:
    missing = [name for name in _REQUIRED if not env.get(name)]
    if missing:
        raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")
    return Settings(
        consumer_key=env["YAHOO_CONSUMER_KEY"],
        consumer_secret=env["YAHOO_CONSUMER_SECRET"],
        refresh_token=env["YAHOO_REFRESH_TOKEN"],
        league_id=env["YAHOO_LEAGUE_ID"],
        port=int(env.get("PORT") or 8080),
    )
