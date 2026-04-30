"""Agent graph nodes — currently only the ranking helper.

The full LangGraph agent (router, retrieval, synthesise) lives outside this
file in branches that have not yet landed. This module exists ahead of that
merge so the absence-aware ranking contract is committed alongside the
pipeline change that produces `score: null` entries.
"""

from __future__ import annotations

from typing import Iterable, Optional


def _rank_score(
    aspects: dict[str, dict],
    weights: dict[str, float],
) -> float:
    """Weighted dot-product rank score that skips null aspects.

    Dimensions whose `aspects[d].score` is `None` are dropped from the
    computation, and the remaining weights are renormalised so that
    "no signal" propagates honestly into the ranking instead of silently
    collapsing to zero or the neutral midpoint.

    Args:
        aspects: Mapping `dim → {score: float | None, ...}` from a
            `SuburbAnalysis.aspects` payload.
        weights: User preference weights per dimension. Values do not need
            to sum to 1; they are renormalised over the surviving dims.

    Returns:
        Weighted-mean rank score in `[0, 1]`. Returns `0.0` when every
        weighted dimension is null (the suburb has no usable signal under
        the user's preferences).
    """
    contributing: list[tuple[float, float]] = []
    for dim, weight in weights.items():
        if weight <= 0:
            continue
        entry = aspects.get(dim)
        if entry is None:
            continue
        score: Optional[float] = entry.get("score")
        if score is None:
            continue
        contributing.append((weight, float(score)))

    total_weight = sum(w for w, _ in contributing)
    if total_weight <= 0:
        return 0.0
    return sum(w * s for w, s in contributing) / total_weight


def _surviving_dimensions(
    aspects: dict[str, dict],
    weights: Iterable[str],
) -> list[str]:
    """Return the subset of `weights` whose aspect score is not null."""
    return [
        d
        for d in weights
        if aspects.get(d, {}).get("score") is not None
    ]
