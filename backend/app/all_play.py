"""All-play: every team against every other team, category by category. Plain Python; see
docs/specs/2026-11-16-all-play-design.md for the rules."""
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from app.config import CATEGORIES, Category
from app.parsing import MatchupResult, TeamStats
from app.rankings import to_number


@dataclass(frozen=True)
class CatScore:
    """Categories won, lost and tied, from one team's side."""
    wins: int
    losses: int
    ties: int


def _pct(wins: int, losses: int, ties: int) -> Fraction:
    """Win % with ties counting half; exact, so equal records compare equal."""
    games = wins + losses + ties
    return Fraction(2 * wins + ties, 2 * games) if games else Fraction(0)


def _cats(score: CatScore) -> Fraction:
    """Categories won, ties counting half."""
    return Fraction(2 * score.wins + score.ties, 2)


@dataclass(frozen=True)
class WeekScore:
    avg_cats: Fraction  # exact; rounded only on output
    wins: int
    losses: int
    ties: int
    vs: dict[str, CatScore]

    @property
    def pct(self) -> Fraction:
        return _pct(self.wins, self.losses, self.ties)


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
        cats = sum((_cats(s) for s in vs.values()), Fraction(0))
        scores[team.team_key] = WeekScore(
            avg_cats=cats / len(vs) if vs else Fraction(0),
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
            "avg_cats": round(float(s.avg_cats), 2),
            "wins": s.wins,
            "losses": s.losses,
            "ties": s.ties,
            "pct": round(float(s.pct), 3),
            "place": 1 + sum(other.avg_cats > s.avg_cats for other in scores.values()),
            "order": position,
            "vs": {k: {"wins": v.wins, "losses": v.losses, "ties": v.ties} for k, v in s.vs.items()},
        }
    return out


@dataclass
class _SeasonTotals:
    name: str
    wins: int = 0
    losses: int = 0
    ties: int = 0
    cats: Fraction = Fraction(0)  # sum of weekly Avg Cats
    weeks: int = 0
    record: CatScore | None = None  # real category W–L–T, weeks with a matchup only
    luck: list[Fraction] = field(default_factory=list)

    @property
    def pct(self) -> Fraction:
        return _pct(self.wins, self.losses, self.ties)

    @property
    def avg_cats(self) -> Fraction:
        return self.cats / self.weeks


def season_all_play(weeks: list[list[TeamStats]], results: list[dict[str, MatchupResult]] | None,
                    categories: Sequence[Category] = CATEGORIES) -> list[dict]:
    """Weekly all-play summed over the given weeks. `results`, when given, is parallel to `weeks`
    and supplies the real Record and Luck; None blanks both for every team."""
    totals: dict[str, _SeasonTotals] = {}
    for index, teams in enumerate(weeks):
        scores = week_scores(teams, categories)
        week_results = results[index] if results is not None else {}
        for team in teams:
            s = scores[team.team_key]
            t = totals.setdefault(team.team_key, _SeasonTotals(team.name))
            t.name = team.name
            t.wins += s.wins
            t.losses += s.losses
            t.ties += s.ties
            t.cats += s.avg_cats
            t.weeks += 1
            real = week_results.get(team.team_key)
            if real is not None:
                r = t.record or CatScore(0, 0, 0)
                t.record = CatScore(r.wins + real.wins, r.losses + real.losses, r.ties + real.ties)
                t.luck.append(_cats(CatScore(real.wins, real.losses, real.ties)) - s.avg_cats)

    ordered = sorted(totals, key=lambda k: (-totals[k].pct, -totals[k].avg_cats, totals[k].name))
    rows = []
    for key in ordered:
        t = totals[key]
        rows.append({
            "team_key": key,
            "name": t.name,
            "place": 1 + sum(other.pct > t.pct for other in totals.values()),
            "wins": t.wins,
            "losses": t.losses,
            "ties": t.ties,
            "pct": round(float(t.pct), 3),
            "avg_cats": round(float(t.avg_cats), 2),
            "weeks": t.weeks,
            "record": None if t.record is None else
            {"wins": t.record.wins, "losses": t.record.losses, "ties": t.record.ties},
            # + 0.0 so a mean that rounds to zero is never sent as -0.0
            "luck": round(float(sum(t.luck) / len(t.luck)), 2) + 0.0 if t.luck else None,
        })
    return rows
