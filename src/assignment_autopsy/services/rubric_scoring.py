"""
The MIT License (MIT)

Copyright (c) 2026-present DA-344 (aka Developer Anonymous)

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations


def level_weight_fraction(position: int, total: int, descending: bool) -> float:
    """Return the score fraction (0..1) earned by a level at `position`.

    `descending=True` means level 0 is the highest-value level (left to right,
    highest to lowest). `descending=False` means level 0 is the lowest-value
    level (left to right, lowest to highest).
    """
    if total <= 0:
        return 0.0
    rank = (total - position) if descending else (position + 1)
    return rank / total


def score_level_criterion(
    criterion_max_points: float | None, position: int, total: int, descending: bool
) -> float | None:
    if criterion_max_points is None:
        return None
    return round(
        criterion_max_points * level_weight_fraction(position, total, descending), 2
    )


def effective_criterion_points(criteria, rubric_max_points: float | None) -> dict[str, float]:
    """Map criterion id -> points it's worth, filling in any criteria left
    without an explicit weight with an even share of the rubric's remaining
    total. Without this, a "levels" rubric whose rows don't all set a weight
    would never earn any points for those rows, and the live grade preview
    (and the saved grade) would stay stuck at 0 no matter what the teacher picks.
    """
    explicit_total = sum(
        criterion.max_points for criterion in criteria if criterion.max_points is not None
    )
    unweighted = [criterion for criterion in criteria if criterion.max_points is None]
    remaining = max(0.0, (rubric_max_points or 0) - explicit_total)
    share = remaining / len(unweighted) if unweighted else 0.0
    return {
        str(criterion.id): (
            criterion.max_points if criterion.max_points is not None else share
        )
        for criterion in criteria
    }



def estimate_ai_grade(
    rubric, criteria, levels, result: dict | None
) -> tuple[float, float] | None:
    """Estimate an approximate AI grade (earned, max) from a stored evaluation result."""
    if not rubric or not result or not result.get("rubric"):
        return None
    level_positions = {level.label: index for index, level in enumerate(levels)}
    criteria_by_id = {str(criterion.id): criterion for criterion in criteria}
    earned = 0.0
    max_total = 0.0
    for item in result["rubric"]:
        criterion = criteria_by_id.get(item.get("criterion_id"))
        if not criterion or criterion.max_points is None:
            continue
        max_total += criterion.max_points
        if item.get("type") == "points":
            points = item.get("estimated_points")
            if points is not None:
                earned += max(0.0, min(float(points), float(criterion.max_points)))
            continue
        label = item.get("estimated_max_level")
        position = level_positions.get(label)
        if position is None or not levels:
            continue
        earned += (
            score_level_criterion(
                criterion.max_points, position, len(levels), rubric.levels_descending
            )
            or 0.0
        )
    if max_total <= 0:
        return None
    return round(earned, 2), round(max_total, 2)
