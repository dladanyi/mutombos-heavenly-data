import json
from pathlib import Path

import pytest

from app.config import CATEGORIES, Category
from app.parsing import TeamStats, parse_team_stats
from app.rankings import build_rankings, to_number

PTS = Category("PTS", "12", True)
TO = Category("TO", "19", False)


def team(name, **values):
    return TeamStats(team_key=f"k.{name}", name=name, values=values)


def ranks(rows, key):
    return {r["name"]: r["stats"][key]["rank"] for r in rows}


@pytest.mark.parametrize("raw, expected", [
    (".482", 0.482), ("0.482", 0.482), ("812", 812), ("-", None), ("", None), (None, None),
    ("301/624", None),
])
def test_to_number(raw, expected):
    assert to_number(raw) == expected
    assert type(to_number(raw)) is type(expected)


def test_higher_is_better_rank():
    rows = build_rankings([team("a", **{"12": "100"}), team("b", **{"12": "90"}), team("c", **{"12": "80"})], [PTS])
    assert ranks(rows, "PTS") == {"a": 1, "b": 2, "c": 3}


def test_turnovers_lower_is_better():
    rows = build_rankings([team("a", **{"19": "10"}), team("b", **{"19": "20"}), team("c", **{"19": "30"})], [TO])
    assert ranks(rows, "TO") == {"a": 1, "b": 2, "c": 3}


def test_ties_use_min_method():
    rows = build_rankings([team("a", **{"12": "100"}), team("b", **{"12": "100"}), team("c", **{"12": "80"})], [PTS])
    assert ranks(rows, "PTS") == {"a": 1, "b": 1, "c": 3}


def test_null_ranks_worst():
    rows = build_rankings([team("a", **{"12": "100"}), team("b", **{"12": "-"}), team("c", **{"12": "80"})], [PTS])
    assert ranks(rows, "PTS") == {"a": 1, "b": 3, "c": 2}
    assert next(r for r in rows if r["name"] == "b")["stats"]["PTS"]["value"] is None


def test_missing_stat_id_counts_as_null():
    rows = build_rankings([team("a", **{"12": "100"}), team("b")], [PTS])
    assert ranks(rows, "PTS") == {"a": 1, "b": 2}


def test_null_turnovers_rank_worst():
    rows = build_rankings([team("a", **{"19": "10"}), team("b", **{"19": "-"})], [TO])
    assert ranks(rows, "TO") == {"a": 1, "b": 2}


def test_avg_rank_rounded_and_sorted():
    # a: PTS 1, TO 2 -> 1.5; b: PTS 2, TO 1 -> 1.5; c: PTS 3, TO 3 -> 3.0
    teams = [team("c", **{"12": "1", "19": "9"}), team("b", **{"12": "5", "19": "1"}),
             team("a", **{"12": "9", "19": "5"})]
    rows = build_rankings(teams, [PTS, TO])
    assert [(r["name"], r["avg_rank"]) for r in rows] == [("a", 1.5), ("b", 1.5), ("c", 3.0)]
    three = [Category(k, k, True) for k in ("1", "2", "3")]
    rows = build_rankings([team("x", **{"1": "1", "2": "1", "3": "2"}), team("y", **{"1": "2", "2": "2", "3": "1"})], three)
    assert rows[0]["avg_rank"] == 1.33


def test_place_uses_min_ties():
    teams = [team("c", **{"12": "1", "19": "9"}), team("b", **{"12": "5", "19": "1"}),
             team("a", **{"12": "9", "19": "5"})]
    rows = build_rankings(teams, [PTS, TO])
    assert [r["place"] for r in rows] == [1, 1, 3]


def test_detail_attached_to_fg_ft():
    t = team("a", **{"5": ".482", "9004003": "301/624", "8": ".800", "9007006": "80/100", "12": "812"})
    row, = build_rankings([t])
    assert row["stats"]["FG%"] == {"value": 0.482, "rank": 1, "detail": "301/624"}
    assert row["stats"]["FT%"]["detail"] == "80/100"
    assert "detail" not in row["stats"]["PTS"]


def test_all_values_missing_ties_everyone():
    teams = [team(n, **{c.stat_id: "-" for c in CATEGORIES}) for n in ("a", "b", "c")]
    rows = build_rankings(teams)
    assert all(cell["rank"] == 3 and cell["value"] is None for r in rows for cell in r["stats"].values())
    assert [r["place"] for r in rows] == [1, 1, 1]
    assert [r["name"] for r in rows] == ["a", "b", "c"]


def test_no_teams():
    assert build_rankings([]) == []


def test_season_fixture_end_to_end():
    payload = json.loads((Path(__file__).parent / "fixtures" / "season_stats.json").read_text())
    rows = build_rankings(parse_team_stats(payload))
    assert len(rows) == 12
    assert all(list(r["stats"]) == [c.key for c in CATEGORIES] for r in rows)
    assert rows[0]["place"] == 1
    assert [r["avg_rank"] for r in rows] == sorted(r["avg_rank"] for r in rows)
    assert set(rows[0]) == {"team_key", "name", "avg_rank", "place", "stats"}


def test_rows_carry_team_key():
    rows = build_rankings([team("a"), team("b")], [PTS])
    assert {r["name"]: r["team_key"] for r in rows} == {"a": "k.a", "b": "k.b"}
