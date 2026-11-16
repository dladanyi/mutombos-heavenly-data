"""All-play: every team against every other team, category by category. Plain Python; see
docs/specs/2026-11-16-all-play-design.md for the rules."""
from collections.abc import Sequence
from dataclasses import dataclass

from app.config import CATEGORIES, Category
from app.parsing import MatchupResult, TeamStats
from app.rankings import to_number


@dataclass(frozen=True)
class CatScore:
    """Categories won, lost and tied, from one team's side."""
    wins: int
    losses: int
    ties: int


@dataclass(frozen=True)
class WeekScore:
    avg_cats: float  # unrounded
    wins: int
    losses: int
    ties: int
    vs: dict[str, CatScore]

    @property
    def pct(self) -> float:
        games = self.wins + self.losses + self.ties
        return (self.wins + 0.5 * self.ties) / games if games else 0.0


def compare(a: TeamStats, b: TeamStats, categories: Sequence[Category] = CATEGORIES) -> CatScore:
    """Higher wins (lower for TO); equal ties; a value beats None; two Nones tie."""
    wins = losses = ties = 0
    for category in categories:
        x = to_number(a.values.get(category.stat_id))
        y = to_number(b.values.get(category.stat_id))
        if x == y:
            ties += 1
        elif y is None or (x is not None and (x > y) == category.higher_is_better):
            wins += 1
        else:
            losses += 1
    return CatScore(wins, losses, ties)


def week_scores(teams: list[TeamStats], categories: Sequence[Category] = CATEGORIES) -> dict[str, WeekScore]:
    scores = {}
    for team in teams:
        vs = {other.team_key: compare(team, other, categories) for other in teams if other is not team}
        cats = sum(s.wins + 0.5 * s.ties for s in vs.values())
        scores[team.team_key] = WeekScore(
            avg_cats=cats / len(vs) if vs else 0.0,
            wins=sum(s.wins > s.losses for s in vs.values()),
            losses=sum(s.wins < s.losses for s in vs.values()),
            ties=sum(s.wins == s.losses for s in vs.values()),
            vs=vs,
        )
    return scores


def week_all_play(teams: list[TeamStats], categories: Sequence[Category] = CATEGORIES) -> dict[str, dict]:
    scores = week_scores(teams, categories)
    names = {t.team_key: t.name for t in teams}
    ordered = sorted(scores, key=lambda k: (-scores[k].avg_cats, -scores[k].pct, names[k]))
    out = {}
    for position, key in enumerate(ordered, start=1):
        s = scores[key]
        out[key] = {
            "avg_cats": round(s.avg_cats, 2),
            "wins": s.wins,
            "losses": s.losses,
            "ties": s.ties,
            "pct": round(s.pct, 3),
            "place": 1 + sum(other.avg_cats > s.avg_cats for other in scores.values()),
            "order": position,
            "vs": {k: {"wins": v.wins, "losses": v.losses, "ties": v.ties} for k, v in s.vs.items()},
        }
    return out


def season_all_play(weeks: list[list[TeamStats]], results: list[dict[str, MatchupResult]] | None,
                    categories: Sequence[Category] = CATEGORIES) -> list[dict]:
    """Weekly all-play summed over the given weeks. `results`, when given, is parallel to `weeks`
    and supplies the real Record and Luck; None blanks both for every team."""
    totals: dict[str, dict] = {}
    for index, teams in enumerate(weeks):
        scores = week_scores(teams, categories)
        week_results = results[index] if results is not None else {}
        for team in teams:
            s = scores[team.team_key]
            t = totals.setdefault(team.team_key, {"wins": 0, "losses": 0, "ties": 0, "cats": 0.0,
                                                  "weeks": 0, "record": None, "luck": []})
            t["name"] = team.name
            t["wins"] += s.wins
            t["losses"] += s.losses
            t["ties"] += s.ties
            t["cats"] += s.avg_cats
            t["weeks"] += 1
            real = week_results.get(team.team_key)
            if real is not None:
                record = t["record"] or {"wins": 0, "losses": 0, "ties": 0}
                t["record"] = {"wins": record["wins"] + real.wins, "losses": record["losses"] + real.losses,
                               "ties": record["ties"] + real.ties}
                t["luck"].append(real.wins + 0.5 * real.ties - s.avg_cats)

    def pct(t: dict) -> float:
        games = t["wins"] + t["losses"] + t["ties"]
        return (t["wins"] + 0.5 * t["ties"]) / games if games else 0.0

    def avg(t: dict) -> float:
        return t["cats"] / t["weeks"]

    ordered = sorted(totals, key=lambda k: (-pct(totals[k]), -avg(totals[k]), totals[k]["name"]))
    rows = []
    for key in ordered:
        t = totals[key]
        luck = round(sum(t["luck"]) / len(t["luck"]), 2) + 0.0 if t["luck"] else None  # + 0.0: no -0.0
        rows.append({
            "team_key": key,
            "name": t["name"],
            "place": 1 + sum(pct(other) > pct(t) for other in totals.values()),
            "wins": t["wins"],
            "losses": t["losses"],
            "ties": t["ties"],
            "pct": round(pct(t), 3),
            "avg_cats": round(avg(t), 2),
            "weeks": t["weeks"],
            "record": t["record"],
            "luck": luck,
        })
    return rows
