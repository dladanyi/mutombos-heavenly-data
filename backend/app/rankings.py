"""Rank teams per category and overall. Plain Python; see spec §5.4 for the rules."""
from collections.abc import Sequence

from app.config import CATEGORIES, Category
from app.parsing import TeamStats

Number = int | float


def to_number(raw: str | None) -> Number | None:
    """'812' -> 812, '.482' -> 0.482; '', '-', None and 'made/attempted' strings -> None."""
    if raw is None:
        return None
    text = raw.strip()
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return None


def build_rankings(teams: list[TeamStats], categories: Sequence[Category] = CATEGORIES) -> list[dict]:
    rows = [{"name": t.name, "stats": {}} for t in teams]
    for category in categories:
        values = [to_number(t.values.get(category.stat_id)) for t in teams]
        for row, team, value, rank in zip(rows, teams, values, _ranks(values, category.higher_is_better)):
            cell = {"value": value, "rank": rank}
            if category.detail_stat_id:
                cell["detail"] = team.values.get(category.detail_stat_id)
            row["stats"][category.key] = cell

    for row in rows:
        ranks = [cell["rank"] for cell in row["stats"].values()]
        row["avg_rank"] = round(sum(ranks) / len(ranks), 2) if ranks else 0.0
    rows.sort(key=lambda r: (r["avg_rank"], r["name"]))
    for row in rows:
        row["place"] = 1 + sum(other["avg_rank"] < row["avg_rank"] for other in rows)
    return [{"name": r["name"], "avg_rank": r["avg_rank"], "place": r["place"], "stats": r["stats"]}
            for r in rows]


def _ranks(values: list[Number | None], higher_is_better: bool) -> list[int]:
    """'min' tie method: ties share the best rank. Missing values rank last (= team count)."""
    present = [v for v in values if v is not None]
    ranks = []
    for value in values:
        if value is None:
            ranks.append(len(values))
        elif higher_is_better:
            ranks.append(1 + sum(other > value for other in present))
        else:
            ranks.append(1 + sum(other < value for other in present))
    return ranks
