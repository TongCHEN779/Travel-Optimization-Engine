"""Pareto dominance utilities (minimisation, integer vectors)."""
from __future__ import annotations

from typing import Callable, Sequence, TypeVar

import numpy as np

T = TypeVar("T")


def dominates(a: Sequence[int], b: Sequence[int]) -> bool:
    """True iff a <= b componentwise and a != b."""
    strictly = False
    for x, y in zip(a, b):
        if x > y:
            return False
        if x < y:
            strictly = True
    return strictly


def pareto_filter(items: Sequence[T], key: Callable[[T], Sequence[int]]) -> list[T]:
    """Return the non-dominated subset, keeping one item per distinct vector.

    Sort lexicographically: if b dominates a then b <=_lex a, so every dominator
    precedes its victim and a single forward pass against the kept set suffices.
    Worst case O(n * |front| * d), vectorised over the kept set with numpy.
    """
    n = len(items)
    if n <= 1:
        return list(items)
    if n <= 24:  # pure Python beats numpy's fixed overhead on tiny sets
        pairs = sorted(((tuple(key(it)), it) for it in items), key=lambda t: t[0])
        kept: list[tuple[tuple[int, ...], T]] = []
        for v, it in pairs:
            for kv, _ in kept:
                if all(a <= b for a, b in zip(kv, v)):
                    break
            else:
                kept.append((v, it))
        return [it for _, it in kept]
    vecs = np.asarray([key(it) for it in items], dtype=np.int64)
    order = np.lexsort(vecs.T[::-1])  # lexicographic by column 0, then 1, ...
    kept_idx: list[int] = []
    kept = np.empty_like(vecs)
    m = 0
    for i in order:
        v = vecs[i]
        # v is dominated (or duplicated) iff some kept row is <= v everywhere
        if m and np.any(np.all(kept[:m] <= v, axis=1)):
            continue
        kept[m] = v
        m += 1
        kept_idx.append(int(i))
    return [items[i] for i in kept_idx]


def front_vectors(items: Sequence[T], key: Callable[[T], Sequence[int]]) -> set[tuple[int, ...]]:
    return {tuple(key(it)) for it in items}


def hypervolume_mc(
    front: np.ndarray, ref: np.ndarray, ideal: np.ndarray, n_samples: int = 20000, seed: int = 0
) -> float:
    """Monte-Carlo hypervolume (fraction of the [ideal, ref] box dominated by `front`).

    Exact hypervolume is #P-hard in the number of objectives; with 5 objectives a
    fixed-seed MC estimate is adequate for comparing algorithms on the same box.
    """
    if len(front) == 0:
        return 0.0
    rng = np.random.default_rng(seed)
    pts = rng.uniform(ideal, ref, size=(n_samples, len(ref)))
    dominated = np.zeros(n_samples, dtype=bool)
    for f in front:
        dominated |= np.all(pts >= f, axis=1)
    return float(dominated.mean())
