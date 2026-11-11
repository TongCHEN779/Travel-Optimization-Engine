"""Reference / baseline algorithms for a single leg.

* brute_force_front : DFS enumeration of every feasible path + Pareto filter.
                      Exponential - the correctness oracle for small instances.
* weighted_sum_best : scalarised DP (one best label per (flight, #stops)).
                      Finds only *supported* Pareto points (convex hull).
* weighted_sum_front: sweeps random weight vectors -> approximate front.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from functools import lru_cache

import numpy as np

from .graph import TemporalGraph, connection_risk_micro
from .models import Itinerary, LegQuery, N_OBJ
from .pareto import pareto_filter

_conn_risk = lru_cache(maxsize=None)(connection_risk_micro)


def brute_force_front(graph: TemporalGraph, q: LegQuery, max_paths: int = 5_000_000) -> list[Itinerary]:
    c = q.constraints
    bounds = c.bounds()
    pax = c.passengers
    flights = graph.usable(q)
    deps = [f.dep for f in flights]
    by_origin: dict[str, list] = {}
    for f in flights:
        by_origin.setdefault(f.origin, []).append(f)
    dep_keys = {o: [f.dep for f in lst] for o, lst in by_origin.items()}
    results: list[Itinerary] = []
    count = 0

    def dfs(path: list[int], last, vec: tuple[int, ...]):
        nonlocal count
        if last.dest == q.dest:
            count += 1
            if count > max_paths:
                raise RuntimeError("brute force path limit exceeded")
            results.append(Itinerary(tuple(path), vec))  # type: ignore[arg-type]
            return  # flights out of dest are excluded, so path ends here
        if vec[2] >= c.max_stops:
            return
        lst = by_origin.get(last.dest, [])
        keys = dep_keys.get(last.dest, [])
        lo = bisect_left(keys, last.arr + c.min_connection)
        hi = bisect_right(keys, last.arr + c.max_layover)
        for g in lst[lo:hi]:
            lay = g.dep - last.arr
            nv = (
                vec[0] + g.price_cents * pax, vec[1] + g.duration + lay, vec[2] + 1,
                vec[3] + lay, vec[4] + g.risk_micro + _conn_risk(lay, c.min_connection),
            )
            if all(x <= b for x, b in zip(nv, bounds)):
                path.append(g.id)
                dfs(path, g, nv)
                path.pop()

    for g in by_origin.get(q.origin, []):
        if q.dep_from <= g.dep <= q.dep_to:
            v = (g.price_cents * pax, g.duration, 0, 0, g.risk_micro)
            if all(x <= b for x, b in zip(v, bounds)):
                dfs([g.id], g, v)
    return pareto_filter(results, key=lambda it: it.vec)


def weighted_sum_best(graph: TemporalGraph, q: LegQuery, weights: tuple[float, ...]) -> Itinerary | None:
    """Minimise w . vec subject to max_stops, via DP over (flight, stops)."""
    c = q.constraints
    pax = c.passengers
    w = np.asarray(weights, dtype=float)
    flights = graph.usable(q)
    allowed = {f.id for f in flights}
    best: dict[tuple[int, int], tuple[float, tuple[int, ...], tuple[int, int] | None]] = {}
    for g in flights:
        if g.origin == q.origin:
            if not (q.dep_from <= g.dep <= q.dep_to):
                continue
            v = (g.price_cents * pax, g.duration, 0, 0, g.risk_micro)
            best[(g.id, 0)] = (float(w @ np.asarray(v)), v, None)
            continue
        for f in graph.predecessors(g, c, allowed):
            lay = g.dep - f.arr
            dv = np.array([g.price_cents * pax, g.duration + lay, 1, lay, g.risk_micro + _conn_risk(lay, c.min_connection)])
            for k in range(c.max_stops):
                prev = best.get((f.id, k))
                if prev is None:
                    continue
                v = tuple(int(a + b) for a, b in zip(prev[1], dv))
                s = float(w @ np.asarray(v))
                cur = best.get((g.id, k + 1))
                if cur is None or s < cur[0]:
                    best[(g.id, k + 1)] = (s, v, (f.id, k))
    top = None
    for (fid, k), val in best.items():
        if graph.by_id[fid].dest == q.dest and (top is None or val[0] < top[1][0]):
            top = ((fid, k), val)
    if top is None:
        return None
    path, cur = [], top[0]
    while cur is not None:
        path.append(cur[0])
        cur = best[cur][2]
    return Itinerary(tuple(reversed(path)), top[1][1])  # type: ignore[arg-type]


def weighted_sum_front(graph: TemporalGraph, q: LegQuery, n_weights: int = 50, seed: int = 0) -> list[Itinerary]:
    """Approximate front by sweeping weights, normalised by a rough objective scale."""
    rng = np.random.default_rng(seed)
    scale = np.array([100_000.0, 600.0, 2.0, 300.0, 300_000.0])  # ~1 "unit" per objective
    found: list[Itinerary] = []
    for _ in range(n_weights):
        lam = rng.dirichlet(np.ones(N_OBJ))
        it = weighted_sum_best(graph, q, tuple(lam / scale))
        if it is not None:
            found.append(it)
    return pareto_filter(found, key=lambda it: it.vec)
