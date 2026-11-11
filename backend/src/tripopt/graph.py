"""Temporal flight graph.

Nodes are *flight events*; an arc f -> g exists iff
    f.dest == g.origin  and  mct <= g.dep - f.arr <= max_layover.
Because every flight has arr > dep and g.dep >= f.arr + mct, the graph is a DAG
ordered by departure time. This makes label-setting exact and simple: process
flights in departure order and every predecessor is already final.
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from typing import Iterable

from .models import Constraints, Flight, LegQuery


def connection_risk_micro(layover: int, mct: int) -> int:
    """Additive risk of a connection: -log(1 - P(miss)) with P(miss) decaying in slack.

    A connection at exactly the minimum connection time misses with prob 0.30;
    each extra hour of slack divides the miss probability by e^(60/45).
    """
    p = 0.30 * math.exp(-(layover - mct) / 45.0)
    return int(round(-math.log(1 - p) * 1e6))


class TemporalGraph:
    def __init__(self, flights: Iterable[Flight]):
        self.flights: list[Flight] = list(flights)
        self.by_id = {f.id: f for f in self.flights}
        self.by_origin: dict[str, list[Flight]] = defaultdict(list)
        self.arrivals: dict[str, list[Flight]] = defaultdict(list)  # sorted by arr
        for f in self.flights:
            self.by_origin[f.origin].append(f)
            self.arrivals[f.dest].append(f)
        for lst in self.by_origin.values():
            lst.sort(key=lambda f: f.dep)
        for lst in self.arrivals.values():
            lst.sort(key=lambda f: f.arr)
        self._arr_keys = {a: [f.arr for f in lst] for a, lst in self.arrivals.items()}
        self._dep_keys = {a: [f.dep for f in lst] for a, lst in self.by_origin.items()}

    def usable(self, q: LegQuery) -> list[Flight]:
        """Flights that can appear on a feasible path for the leg query, by departure.

        Layered forward BFS from the admissible first flights, expanding at most
        `max_stops` times and never past the destination. Exact local filters:
        never fly *into* the origin or *out of* the destination (only dominated
        detours), and drop flights without enough seats. Output-sensitive: work is
        proportional to the reachable subgraph, not to the whole schedule.
        """
        c = q.constraints
        ok = lambda f: f.dest != q.origin and f.origin != q.dest and f.seats >= c.passengers  # noqa: E731
        keys = self._dep_keys.get(q.origin, [])
        lo, hi = bisect_left(keys, q.dep_from), bisect_right(keys, q.dep_to)
        layer = [f for f in self.by_origin.get(q.origin, [])[lo:hi] if ok(f)]
        seen = {f.id: f for f in layer}
        for _ in range(c.max_stops):
            nxt = []
            for f in layer:
                if f.dest == q.dest:
                    continue
                ks = self._dep_keys.get(f.dest)
                if not ks:
                    continue
                a, b = bisect_left(ks, f.arr + c.min_connection), bisect_right(ks, f.arr + c.max_layover)
                for g in self.by_origin[f.dest][a:b]:
                    if g.id not in seen and ok(g):
                        seen[g.id] = g
                        nxt.append(g)
            layer = nxt
            if not layer:
                break
        return sorted(seen.values(), key=lambda f: f.dep)

    def predecessors(self, g: Flight, c: Constraints, allowed: set[int]) -> list[Flight]:
        """Flights f with arrival in [g.dep - max_layover, g.dep - mct] into g.origin."""
        keys = self._arr_keys.get(g.origin)
        if not keys:
            return []
        lo = bisect_left(keys, g.dep - c.max_layover)
        hi = bisect_right(keys, g.dep - c.min_connection)
        return [f for f in self.arrivals[g.origin][lo:hi] if f.id in allowed]
