import json
from pathlib import Path

from app.all_play import CatScore, compare, season_all_play, week_all_play
from app.config import Category
from app.parsing import MatchupResult, TeamStats, parse_scoreboard, parse_team_stats

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


# A and B played each other for real; C had a bye.
RES = {"A": MatchupResult("W", 2, 0, 1, "B", "B"), "B": MatchupResult("L", 0, 2, 1, "A", "A")}


def test_two_identical_weeks_sum_and_average():
    rows = season_all_play([[A, B, C], [A, B, C]], [RES, RES], CATS)
    assert [r["team_key"] for r in rows] == ["A", "B", "C"]
    a = rows[0]
    assert (a["wins"], a["losses"], a["ties"], a["pct"], a["avg_cats"], a["weeks"]) == (4, 0, 0, 1.0, 2.25, 2)
    assert (a["name"], a["place"]) == ("A", 1)
    assert a["record"] == {"wins": 4, "losses": 0, "ties": 2}
    assert a["luck"] == 0.25  # 2.5 real categories − 2.25 Avg Cats, each week
    assert rows[1]["luck"] == -0.75  # 0.5 − 1.25


def test_bye_counts_for_all_play_but_not_record_or_luck():
    c = season_all_play([[A, B, C]], [RES], CATS)[2]
    assert (c["team_key"], c["wins"], c["losses"]) == ("C", 0, 2)
    assert c["record"] is None and c["luck"] is None


def test_team_missing_from_a_week_averaged_over_its_weeks():
    rows = {r["team_key"]: r for r in season_all_play([[A, B], [A, B, C]], None, CATS)}
    assert rows["C"]["weeks"] == 1 and rows["C"]["avg_cats"] == 1.0
    assert rows["A"]["weeks"] == 2 and rows["A"]["wins"] == 3


def test_no_results_blanks_record_and_luck_for_everyone():
    assert all(r["record"] is None and r["luck"] is None
               for r in season_all_play([[A, B, C]], None, CATS))


def test_season_place_by_win_pct_then_avg_cats_orders():
    week = [stats("W", 0, 0, 0), stats("X", 0, 0, 1), stats("Y", 0, 0, 2), stats("Z", 0, 1, 1)]
    rows = season_all_play([week], None, (PTS, REB, AST))
    # Y and Z both have Win % .833; Z averages 2.0 categories, Y 1.83.
    assert [r["team_key"] for r in rows] == ["Z", "Y", "X", "W"]
    assert [r["place"] for r in rows] == [1, 1, 3, 4]
    assert (rows[0]["pct"], rows[1]["pct"]) == (0.833, 0.833)


def test_zero_luck_is_not_negative_zero():
    p = TeamStats("P", "P", {"12": "100"})
    q = TeamStats("Q", "Q", {"12": "90"})
    res = {"P": MatchupResult("W", 1, 0, 0, "Q", "Q"), "Q": MatchupResult("L", 0, 1, 0, "P", "P")}
    rows = season_all_play([[p, q]], [res], (PTS,))
    assert [r["luck"] for r in rows] == [0.0, 0.0]
    assert [str(r["luck"]) for r in rows] == ["0.0", "0.0"]


def test_name_comes_from_the_latest_week():
    renamed = TeamStats("A", "A2", A.values)
    rows = season_all_play([[A, B], [renamed, B]], None, CATS)
    assert rows[0]["name"] == "A2"


def test_no_weeks():
    assert season_all_play([], None) == []


def test_equal_season_averages_tie_break_by_name_despite_float_order():
    # One category, four teams. Zed's weekly Avg Cats are 1, 1/6, 1/6; Abe's are 1/6, 1/6, 1.
    # Mathematically equal (and equal Win %), but the float means differ by the order added
    # (Zed's comes out 1 ulp higher), so only exact arithmetic lets the name decide.
    def week(abe, zed):
        filler = "10" if 200 in (abe, zed) else "50"
        return [TeamStats("Abe", "Abe", {"12": str(abe)}), TeamStats("Zed", "Zed", {"12": str(zed)}),
                TeamStats("F1", "F1", {"12": filler}), TeamStats("F2", "F2", {"12": "100"})]
    rows = season_all_play([week(10, 200), week(10, 10), week(200, 10)], None, (PTS,))
    keys = [r["team_key"] for r in rows]
    abe, zed = rows[keys.index("Abe")], rows[keys.index("Zed")]
    assert (abe["pct"], abe["avg_cats"]) == (zed["pct"], zed["avg_cats"])
    assert keys.index("Abe") < keys.index("Zed")
