import json
from pathlib import Path

from app.all_play import CatScore, compare, week_all_play
from app.config import Category
from app.parsing import TeamStats, parse_scoreboard, parse_team_stats

FIXTURES = Path(__file__).parent / "fixtures"

PTS = Category("PTS", "12", True)
REB = Category("REB", "15", True)
AST = Category("AST", "16", True)
TO = Category("TO", "19", False)
CATS = (PTS, REB, TO)

A = TeamStats("A", "A", {"12": "100", "15": "50", "19": "10"})
B = TeamStats("B", "B", {"12": "90", "15": "50", "19": "12"})
C = TeamStats("C", "C", {"12": "80", "15": "60"})  # no TO value


def load(name):
    return json.loads((FIXTURES / name).read_text())


def stats(key, pts, reb, ast):
    return TeamStats(key, key, {"12": str(pts), "15": str(reb), "16": str(ast)})


def test_compare_counts_wins_ties_and_turnovers():
    assert compare(A, B, CATS) == CatScore(2, 0, 1)
    assert compare(B, A, CATS) == CatScore(0, 2, 1)


def test_value_beats_missing_and_two_missing_tie():
    assert compare(A, C, CATS) == CatScore(2, 1, 0)  # TO: A has a value, C has none
    empty = TeamStats("E", "E", {})
    assert compare(C, empty, CATS) == CatScore(2, 0, 1)  # PTS, REB to C; TO None vs None ties


def test_week_all_play_values_and_order():
    out = week_all_play([C, B, A], CATS)
    assert out["A"] == {"avg_cats": 2.25, "wins": 2, "losses": 0, "ties": 0, "pct": 1.0,
                        "place": 1, "order": 1,
                        "vs": {"B": {"wins": 2, "losses": 0, "ties": 1},
                               "C": {"wins": 2, "losses": 1, "ties": 0}}}
    assert (out["B"]["avg_cats"], out["B"]["pct"], out["B"]["place"], out["B"]["order"]) == (1.25, 0.5, 2, 2)
    assert (out["C"]["avg_cats"], out["C"]["pct"], out["C"]["place"], out["C"]["order"]) == (1.0, 0.0, 3, 3)


def test_equal_avg_cats_share_place_and_win_pct_breaks_order():
    teams = [stats("W", 0, 0, 0), stats("X", 0, 0, 1), stats("Y", 1, 1, 1), stats("Z", 2, 2, 0)]
    out = week_all_play(teams, (PTS, REB, AST))
    # Y and Z both average 6.5/3 categories; Z won all 3 matchups, Y 2 of 3.
    assert out["Y"]["avg_cats"] == out["Z"]["avg_cats"] == 2.17
    assert (out["Z"]["place"], out["Y"]["place"]) == (1, 1)
    assert (out["Z"]["order"], out["Y"]["order"]) == (1, 2)
    assert (out["Z"]["pct"], out["Y"]["pct"]) == (1.0, 0.667)
    assert (out["X"]["place"], out["W"]["place"]) == (3, 4)


def test_name_breaks_a_full_tie_in_order():
    out = week_all_play([stats("Bb", 1, 1, 1), stats("Aa", 1, 1, 1)], (PTS, REB, AST))
    assert (out["Aa"]["order"], out["Bb"]["order"]) == (1, 2)
    assert (out["Aa"]["place"], out["Bb"]["place"]) == (1, 1)


def test_week_before_any_games_all_tie():
    teams = [TeamStats(k, k, {}) for k in ("X", "Y", "Z")]
    out = week_all_play(teams)  # the real 9 categories
    assert all(v["avg_cats"] == 4.5 and v["ties"] == 2 and v["wins"] == 0 and v["place"] == 1
               for v in out.values())


def test_empty_and_single_team():
    assert week_all_play([]) == {}
    assert week_all_play([A], CATS)["A"] == {"avg_cats": 0.0, "wins": 0, "losses": 0, "ties": 0,
                                             "pct": 0.0, "place": 1, "order": 1, "vs": {}}


def test_matches_yahoo_scoreboard_on_real_week():
    teams = {t.team_key: t for t in parse_team_stats(load("week_stats.json"))}
    results = parse_scoreboard(load("scoreboard.json"))
    assert results
    for key, r in results.items():
        assert compare(teams[key], teams[r.opponent_key]) == CatScore(r.wins, r.losses, r.ties), key
