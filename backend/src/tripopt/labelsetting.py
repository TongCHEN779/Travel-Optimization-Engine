"""Exact multi-objective label-setting over the temporal flight DAG.

Label  = (objective vector, parent pointer) attached to a *flight node* g and
         describing a Pareto-candidate path from the origin that ends by flying g.
Rule   = for every g (in departure order) extend labels from all feasible
         predecessor flights, then keep only the non-dominated ones.

Why dominance pruning at a flight node is exact: every extension of a label at
g adds a vector that depends only on the next flight and on g's arrival time -
identical for all labels at g. Hence if a dominates b at g, a + Delta dominates
b + Delta for every continuation Delta, and b can never be part of a Pareto-
optimal complete path. Hard upper bounds are monotone (costs are >= 0), so
labels exceeding a bound are discarded immediately.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .graph import TemporalGraph, connection_risk_micro
from .models import Flight, Itinerary, LegQuery, MINUTES_PER_DAY
from .pareto import pareto_filter

_conn_risk = lru_cache(maxsize=None)(connection_risk_micro)


@dataclass
class SearchStats:
    nodes: int = 0
    generated: int = 0  # candidate labels created
    kept: int = 0  # labels surviving dominance pruning
    pruned_by_bound: int = 0

    @property
    def prune_ratio(self) -> float:
        return 1 - self.kept / self.generated if self.generated else 0.0


def _search(graph: TemporalGraph, q: LegQuery, stats: SearchStats):
    c = q.constraints
    bounds = c.bounds()
    # stops are checked before extension; only the other finite bounds need a per-label test
    finite = [(i, b) for i, b in enumerate(bounds) if i != 2 and b != float("inf")]
    max_stops = c.max_stops
    pax = c.passengers
    flights = graph.usable(q)
    allowed = {f.id for f in flights}
    labels: dict[int, list[tuple[tuple[int, ...], tuple[int, int] | None]]] = {}

    for g in flights:
        is_start = g.origin == q.origin
        if is_start and not (q.dep_from <= g.dep <= q.dep_to):
            continue
        stats.nodes += 1
        pg = g.price_cents * pax
        dg = g.duration
        cands: list[tuple[tuple[int, ...], tuple[int, int] | None]] = []
        if is_start:
            v = (pg, dg, 0, 0, g.risk_micro)
            stats.generated += 1
            if all(x <= b for x, b in zip(v, bounds)):
                cands.append((v, None))
            else:
                stats.pruned_by_bound += 1
        else:
            for f in graph.predecessors(g, c, allowed):
                fl = labels.get(f.id)
                if not fl:
                    continue
                lay = g.dep - f.arr
                dv = (pg, dg + lay, 1, lay, g.risk_micro + _conn_risk(lay, c.min_connection))
                for idx, (pv, _) in enumerate(fl):
                    if pv[2] >= max_stops:  # no connection budget left
                        continue
                    v = (pv[0] + dv[0], pv[1] + dv[1], pv[2] + 1, pv[3] + dv[3], pv[4] + dv[4])
                    stats.generated += 1
                    if finite and any(v[i] > b for i, b in finite):
                        stats.pruned_by_bound += 1
                    else:
                        cands.append((v, (f.id, idx)))
        if cands:
            kept = pareto_filter(cands, key=lambda t: t[0])
            labels[g.id] = kept
            stats.kept += len(kept)
    return labels


def _reconstruct(labels, fid: int, idx: int) -> tuple[int, ...]:
    path = []
    cur: tuple[int, int] | None = (fid, idx)
    while cur is not None:
        path.append(cur[0])
        cur = labels[cur[0]][cur[1]][1]
    return tuple(reversed(path))


def leg_fronts(
    graph: TemporalGraph, q: LegQuery, by_arrival_day: bool = False, stats: SearchStats | None = None
) -> dict[int, list[Itinerary]]:
    """Pareto fronts for a single leg, optionally one front per arrival day.

    Per-day fronts are needed for round trips: the stay-length constraint couples
    the legs through calendar days, so an outbound path may only be discarded if
    it is dominated by another path arriving on the *same* day.
    """
    stats = stats if stats is not None else SearchStats()
    labels = _search(graph, q, stats)
    groups: dict[int, list[Itinerary]] = {}
    for fid, lst in labels.items():
        f = graph.by_id[fid]
        if f.dest != q.dest:
            continue
        key = f.arr_day if by_arrival_day else 0
        for idx, (v, _) in enumerate(lst):
            groups.setdefault(key, []).append(Itinerary(_reconstruct(labels, fid, idx), v))  # type: ignore[arg-type]
    return {k: pareto_filter(v, key=lambda it: it.vec) for k, v in groups.items()}


def leg_front(graph: TemporalGraph, q: LegQuery, stats: SearchStats | None = None) -> list[Itinerary]:
    return leg_fronts(graph, q, False, stats).get(0, [])
