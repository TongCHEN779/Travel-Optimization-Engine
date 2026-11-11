"""Leg model as a MILP (HiGHS via scipy) + epsilon-constraint front enumeration.

Formulation (unit flow on the connection DAG):
    s_g in {0,1}  path starts with flight g          (g departs the origin in window)
    z_fg in {0,1} path connects flight f -> flight g (arc exists iff layover feasible)
    e_g in {0,1}  path ends with flight g            (g arrives at the destination)

    sum_g s_g = 1,   sum_g e_g = 1
    s_g + sum_f z_fg = e_g + sum_h z_gh              for every flight g   (flow conservation)
    sum z <= max_stops
    objective_k(x) <= eps_k                          (epsilon constraints)

All five objectives are linear in (s, z), so the model is exact. Each solve
minimises one primary objective subject to epsilon bounds on the others; a
second lexicographic stage guarantees the returned point is Pareto-optimal.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import product

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from .graph import TemporalGraph, connection_risk_micro
from .models import Itinerary, LegQuery, N_OBJ, OBJECTIVES
from .pareto import pareto_filter

_conn_risk = lru_cache(maxsize=None)(connection_risk_micro)


class LegMILP:
    def __init__(self, graph: TemporalGraph, q: LegQuery):
        c = q.constraints
        self.c, self.q, self.graph = c, q, graph
        pax = c.passengers
        flights = graph.usable(q)
        # forward reachability by number of connections keeps the model small
        starts = [g for g in flights if g.origin == q.origin and q.dep_from <= g.dep <= q.dep_to]
        allowed = {f.id for f in flights}
        reach = {g.id for g in starts}
        frontier = set(reach)
        arcs: list[tuple[int, int]] = []
        for _ in range(c.max_stops):
            nxt: set[int] = set()
            for fid in frontier:
                f = graph.by_id[fid]
                for g in graph.by_origin.get(f.dest, []):
                    if g.id in allowed and f.arr + c.min_connection <= g.dep <= f.arr + c.max_layover:
                        arcs.append((fid, g.id))
                        nxt.add(g.id)
            frontier = nxt
            reach |= nxt
        arcs = sorted(set(arcs))
        ids = sorted(reach)
        self.starts = [g.id for g in starts]
        self.ends = [fid for fid in ids if graph.by_id[fid].dest == q.dest]
        nS, nZ, nE = len(self.starts), len(arcs), len(self.ends)
        self.nvar = nS + nZ + nE
        cost = np.zeros((N_OBJ, self.nvar))
        for i, fid in enumerate(self.starts):
            g = graph.by_id[fid]
            cost[:, i] = (g.price_cents * pax, g.duration, 0, 0, g.risk_micro)
        for j, (a, b) in enumerate(arcs):
            f, g = graph.by_id[a], graph.by_id[b]
            lay = g.dep - f.arr
            cost[:, nS + j] = (g.price_cents * pax, g.duration + lay, 1, lay, g.risk_micro + _conn_risk(lay, c.min_connection))
        self.cost = cost
        row_of = {fid: r for r, fid in enumerate(ids)}
        rows, cols, vals = [], [], []
        for i, fid in enumerate(self.starts):
            rows.append(row_of[fid]); cols.append(i); vals.append(1.0)
        for j, (a, b) in enumerate(arcs):
            rows.append(row_of[b]); cols.append(nS + j); vals.append(1.0)   # inflow to b
            rows.append(row_of[a]); cols.append(nS + j); vals.append(-1.0)  # outflow of a
        for k, fid in enumerate(self.ends):
            rows.append(row_of[fid]); cols.append(nS + nZ + k); vals.append(-1.0)
        A_flow = coo_matrix((vals, (rows, cols)), shape=(len(ids), self.nvar)).tocsr()
        one_s = np.zeros(self.nvar); one_s[:nS] = 1
        one_e = np.zeros(self.nvar); one_e[nS + nZ:] = 1
        self.base = [
            LinearConstraint(A_flow, 0, 0),
            LinearConstraint(one_s[None, :], 1, 1),
            LinearConstraint(one_e[None, :], 1, 1),
        ]
        self.arcs, self.nS, self.nZ = arcs, nS, nZ
        self.n_solves = 0

    def _solve(self, obj: np.ndarray, ub: np.ndarray):
        if self.nS == 0 or not self.ends:
            return None
        cons = list(self.base)
        for k in range(N_OBJ):
            if np.isfinite(ub[k]):
                cons.append(LinearConstraint(self.cost[k][None, :], -np.inf, ub[k]))
        self.n_solves += 1
        res = milp(obj, constraints=cons, integrality=np.ones(self.nvar), bounds=Bounds(0, 1))
        return res.x if res.success else None

    def _decode(self, x: np.ndarray) -> Itinerary:
        x = np.round(x).astype(int)
        start = self.starts[int(np.argmax(x[: self.nS]))]
        nxt = {a: b for j, (a, b) in enumerate(self.arcs) if x[self.nS + j]}
        path = [start]
        while path[-1] in nxt:
            path.append(nxt[path[-1]])
        vec = tuple(int(round(v)) for v in self.cost @ x)
        return Itinerary(tuple(path), vec)  # type: ignore[arg-type]

    def solve(self, primary: int, eps: dict[int, float] | None = None) -> Itinerary | None:
        """min objective[primary] s.t. objective[k] <= eps[k]; Pareto-optimal tie-break."""
        ub = np.full(N_OBJ, np.inf)
        ub[2] = self.c.max_stops
        for k, b in (eps or {}).items():
            ub[k] = min(ub[k], b)
        for k, b in enumerate(self.c.bounds()):
            ub[k] = min(ub[k], b)
        x = self._solve(self.cost[primary], ub)
        if x is None:
            return None
        best = self._decode(x)
        # stage 2: fix primary at optimum, minimise a positive weighted sum of the rest
        ub2 = ub.copy(); ub2[primary] = best.vec[primary]
        scale = np.array([max(1.0, v) for v in best.vec], dtype=float)
        w = 1.0 / scale
        w[primary] = 0.0
        x2 = self._solve(w @ self.cost, ub2)
        return self._decode(x2) if x2 is not None else best


def epsilon_constraint_front(
    graph: TemporalGraph, q: LegQuery, grid: int = 4, primary: int = 0
) -> tuple[list[Itinerary], int]:
    """Approximate Pareto front by sweeping an epsilon grid over non-primary objectives.

    1. Payoff table: ideal/nadir of every objective (lexicographic minimisations).
    2. For each integer value of `stops` and a `grid`-point lattice over the
       remaining continuous objectives, solve min price s.t. objective_k <= eps_k.
    Cost grows as grid^(d-2): the standard curse of the epsilon-constraint method.
    Returns (front, number of MILP solves).
    """
    m = LegMILP(graph, q)
    others = [k for k in range(N_OBJ) if k != primary]
    ideal, nadir = {}, {}
    for k in range(N_OBJ):
        it = m.solve(k)
        if it is None:
            return [], m.n_solves
        ideal[k] = it.vec[k]
    # nadir estimated from the payoff table: worst value of k seen while minimising others
    pay = {k: m.solve(k) for k in range(N_OBJ)}
    for k in range(N_OBJ):
        nadir[k] = max(p.vec[k] for p in pay.values() if p is not None)
    cont = [k for k in others if k != 2]  # stops handled as exact integers
    axes = []
    for k in cont:
        lo, hi = ideal[k], nadir[k]
        axes.append(np.unique(np.round(np.linspace(lo, hi, grid)).astype(int)))
    stop_levels = range(ideal[2], min(q.constraints.max_stops, nadir[2]) + 1)
    found: list[Itinerary] = []
    for s, combo in product(stop_levels, product(*axes)):
        eps = {2: s, **{k: float(v) for k, v in zip(cont, combo)}}
        it = m.solve(primary, eps)
        if it is not None:
            found.append(it)
    return pareto_filter(found, key=lambda it: it.vec), m.n_solves
