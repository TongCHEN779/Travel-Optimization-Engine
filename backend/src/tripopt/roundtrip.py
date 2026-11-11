"""Round-trip optimisation = two leg searches + exact stay-coupled combination.

Objective vectors of the two legs add. The only coupling is the stay length in
calendar days: stay = return_departure_day - outbound_arrival_day must lie in
[min_stay, max_stay]. Therefore:

  * outbound fronts are computed *per arrival day*,
  * inbound  fronts are computed *per departure day*,
  * for each return day r we pool the outbound fronts whose arrival day is
    admissible, Pareto-filter the pool, and take the Minkowski sum with the
    inbound front of day r.

This is exact: if a leg path is dominated by another path with the same coupling
key, swapping it in yields a dominating round trip with the same feasibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .graph import TemporalGraph
from .labelsetting import SearchStats, leg_fronts
from .models import MINUTES_PER_DAY, Itinerary, LegQuery, RoundTripQuery
from .pareto import pareto_filter


@dataclass
class RoundTripResult:
    front: list[Itinerary]
    stats: SearchStats = field(default_factory=SearchStats)
    n_combinations: int = 0


def optimize_round_trip(graph: TemporalGraph, q: RoundTripQuery) -> RoundTripResult:
    stats = SearchStats()
    c = q.constraints
    out_q = LegQuery(
        q.origin, q.dest, q.depart_from_day * MINUTES_PER_DAY, (q.depart_to_day + 1) * MINUTES_PER_DAY - 1, c
    )
    out_by_day = leg_fronts(graph, out_q, by_arrival_day=True, stats=stats)
    if not out_by_day:
        return RoundTripResult([], stats)

    ret_days = sorted({a + s for a in out_by_day for s in range(q.min_stay_days, q.max_stay_days + 1)})
    in_by_day: dict[int, list[Itinerary]] = {}
    for r in ret_days:
        iq = LegQuery(q.dest, q.origin, r * MINUTES_PER_DAY, (r + 1) * MINUTES_PER_DAY - 1, c)
        front = leg_fronts(graph, iq, by_arrival_day=False, stats=stats).get(0, [])
        if front:
            in_by_day[r] = front

    totals = (c.max_price_cents, c.max_duration, None, c.max_wait, c.max_risk_micro)
    results: list[Itinerary] = []
    n_comb = 0
    for r, back in in_by_day.items():
        pool = [it for a, lst in out_by_day.items() if q.min_stay_days <= r - a <= q.max_stay_days for it in lst]
        if not pool:
            continue
        pool = pareto_filter(pool, key=lambda it: it.vec)
        A = np.asarray([it.vec for it in pool], dtype=np.int64)
        B = np.asarray([it.vec for it in back], dtype=np.int64)
        S = (A[:, None, :] + B[None, :, :]).reshape(-1, A.shape[1])
        n_comb += len(S)
        ok = np.ones(len(S), dtype=bool)
        for k, lim in enumerate(totals):
            if lim is not None:
                ok &= S[:, k] <= lim
        idx = np.flatnonzero(ok)
        if not len(idx):
            continue
        cand = [
            Itinerary(pool[i // len(back)].flights + back[i % len(back)].flights, tuple(int(x) for x in S[i]), len(pool[i // len(back)].flights))  # type: ignore[arg-type]
            for i in idx
        ]
        results.extend(pareto_filter(cand, key=lambda it: it.vec))
    return RoundTripResult(pareto_filter(results, key=lambda it: it.vec), stats, n_comb)
