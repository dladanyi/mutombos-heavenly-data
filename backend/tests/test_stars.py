from app.parsing import RankedPlayer, TeamStats
from app.stars import LEVELS, build_star_power


def player(rank, owner=None, kind=None):
    kind = kind or ("team" if owner else "freeagents")
    return RankedPlayer(rank, f"p.{rank}", f"Player {rank}", "SAS", "C", kind, owner)


def teams(*names):
    return [TeamStats(f"k.{n}", n, {}) for n in names]


def rows(result):
    return [(t["name"], t["place"], t["counts"]) for t in result["teams"]]


def test_levels():
    assert LEVELS == (10, 25, 50)


def test_counts_are_cumulative_and_order_is_top10_then_25_then_50():
    # A: one top-10 and four 26-50; B: two top-10; C: one top-10 and two 11-25
    players = [player(1, "k.A"), player(2, "k.B"), player(3, "k.B"), player(4, "k.C"),
               player(12, "k.C"), player(20, "k.C")] + [player(r, "k.A") for r in (30, 31, 40, 45)]
    result = build_star_power(players, teams("A", "B", "C"))
    assert rows(result) == [("B", 1, {"10": 2, "25": 2, "50": 2}),
                            ("C", 2, {"10": 1, "25": 3, "50": 3}),
                            ("A", 3, {"10": 1, "25": 1, "50": 5})]


def test_ties_share_place_and_sort_by_name():
    result = build_star_power([player(1, "k.Z"), player(2, "k.A")], teams("Z", "A", "M"))
    assert rows(result) == [("A", 1, {"10": 1, "25": 1, "50": 1}),
                            ("Z", 1, {"10": 1, "25": 1, "50": 1}),
                            ("M", 3, {"10": 0, "25": 0, "50": 0})]


def test_team_without_stars_listed_with_zero_counts():
    result = build_star_power([], teams("A"))
    assert result["teams"] == [{"team_key": "k.A", "name": "A", "place": 1,
                                "counts": {"10": 0, "25": 0, "50": 0}, "players": []}]


def test_players_listed_in_rank_order_per_team():
    result = build_star_power([player(30, "k.A"), player(5, "k.A")], teams("A"))
    assert result["teams"][0]["players"] == [
        {"rank": 5, "player_key": "p.5", "name": "Player 5", "nba_team": "SAS", "position": "C"},
        {"rank": 30, "player_key": "p.30", "name": "Player 30", "nba_team": "SAS", "position": "C"}]


def test_unowned_and_unknown_owner_go_to_unowned():
    players = [player(7), player(9, kind="waivers"), player(11, "k.GONE"), player(60, "k.A")]
    result = build_star_power(players, teams("A"))
    assert [(u["rank"], u["status"]) for u in result["unowned"]] == [(7, "freeagents"), (9, "waivers"), (11, "team")]
    assert result["teams"][0]["counts"] == {"10": 0, "25": 0, "50": 0}  # rank 60 is outside the top 50


def test_all_teams_tied_share_place_one():
    result = build_star_power([], teams("B", "A", "C"))
    assert [(t["name"], t["place"]) for t in result["teams"]] == [("A", 1), ("B", 1), ("C", 1)]
