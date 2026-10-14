import pytest

from app.config import CATEGORIES, ConfigError, load_settings
from app.errors import YahooFormatError, YahooUnavailable

REQUIRED = {
    "YAHOO_CONSUMER_KEY": "k",
    "YAHOO_CONSUMER_SECRET": "s",
    "YAHOO_REFRESH_TOKEN": "r",
    "YAHOO_LEAGUE_ID": "123",
}


def test_load_settings_reads_required_vars():
    s = load_settings(REQUIRED)
    assert (s.consumer_key, s.consumer_secret, s.refresh_token, s.league_id) == ("k", "s", "r", "123")


def test_port_is_ignored():
    s = load_settings({**REQUIRED, "PORT": "not-a-number"})
    assert not hasattr(s, "port")


@pytest.mark.parametrize("missing", list(REQUIRED))
def test_missing_var_raises_config_error_naming_it(missing):
    env = {k: v for k, v in REQUIRED.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        load_settings(env)


def test_empty_string_counts_as_missing():
    with pytest.raises(ConfigError, match="YAHOO_LEAGUE_ID"):
        load_settings({**REQUIRED, "YAHOO_LEAGUE_ID": ""})


def test_error_message_never_contains_values():
    with pytest.raises(ConfigError) as exc:
        load_settings({**REQUIRED, "YAHOO_CONSUMER_SECRET": "", "YAHOO_REFRESH_TOKEN": "tok-value"})
    assert "tok-value" not in str(exc.value)


def test_categories_order_and_flags():
    assert [c.key for c in CATEGORIES] == ["PTS", "REB", "AST", "ST", "BLK", "3PTM", "FG%", "FT%", "TO"]
    assert [c.key for c in CATEGORIES if not c.higher_is_better] == ["TO"]
    fg = next(c for c in CATEGORIES if c.key == "FG%")
    assert (fg.stat_id, fg.detail_stat_id, fg.detail_label) == ("5", "9004003", "FGM/FGA")
    ft = next(c for c in CATEGORIES if c.key == "FT%")
    assert (ft.stat_id, ft.detail_stat_id, ft.detail_label) == ("8", "9007006", "FTM/FTA")
    assert [c.stat_id for c in CATEGORIES] == ["12", "15", "16", "17", "18", "10", "5", "8", "19"]


def test_yahoo_format_error_is_unavailable():
    assert issubclass(YahooFormatError, YahooUnavailable)
