"""Decision support on top of the Pareto front: weighted ranking and knee point."""
from __future__ import annotations

import numpy as np

from .models import N_OBJ, Itinerary


def normalise(front: list[Itinerary]) -> np.ndarray:
    """Min-max normalise each objective over the front into [0, 1] (0 = best)."""
    M = np.asarray([it.vec for it in front], dtype=float)
    lo, hi = M.min(axis=0), M.max(axis=0)
    span = np.where(hi > lo, hi - lo, 1.0)
    return (M - lo) / span


def weighted_scores(front: list[Itinerary], weights: tuple[float, ...] | None) -> np.ndarray:
    """Lower is better. Weights are re-normalised to sum to 1; default = equal."""
    w = np.ones(N_OBJ) if weights is None else np.asarray(weights, dtype=float)
    w = w / w.sum() if w.sum() > 0 else np.ones(N_OBJ) / N_OBJ
    return normalise(front) @ w


def knee_index(front: list[Itinerary]) -> int:
    """Compromise point: closest to the ideal point in normalised space (L2)."""
    return int(np.argmin(np.linalg.norm(normalise(front), axis=1)))
