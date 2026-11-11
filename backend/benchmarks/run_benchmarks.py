"""Leg-level benchmark: exact label-setting vs brute force vs MILP eps-constraint vs weighted-sum.

    python benchmarks/run_benchmarks.py [--quick]

Metrics per (scale, algorithm), averaged over the same fixed set of OD queries:
  time_ms, front size, recall (fraction of the exact Pareto front recovered),
  hv_ratio (Monte-Carlo hypervolume relative to the exact front; 1.0 = same).
"""
from __future__ import annotations

import argparse
import csv
import random
import statistics as st
import time
from pathlib import Path

import numpy as np

from tripopt.baselines import brute_force_front, weighted_sum_front
from tripopt.graph import TemporalGraph
from tripopt.labelsetting import SearchStats, leg_front
from tripopt.milp import epsilon_constraint_front
from tripopt.models import Constraints, LegQuery, MINUTES_PER_DAY as D
from tripopt.pareto import hypervolume_mc
from tripopt.synthetic import SyntheticConfig, generate

SCALES = {  # name: (airports, hubs, days, window_days, flights/route/day, max_stops)
    "S": (12, 2, 4, 2, 2, 2),
    "M": (30, 4, 10, 3, 2, 2),
    "L": (60, 6, 21, 4, 2, 2),
    "XL": (120, 10, 21, 4, 2, 2),
    # dense hub schedules + 3 connections: path count explodes, brute force must give up
    "D-3stop": (20, 3, 6, 2, 8, 3),
}
BRUTE_FORCE_SCALES = {"S", "M", "D-3stop"}


def timed(fn):
    t = time.perf_counter()
    r = fn()
    return r, (time.perf_counter() - t) * 1000


def run(quick: bool, n_queries: int, out_dir: Path):
    rows = []
    for name, (na, nh, days, win, fpd, ms) in SCALES.items():
        if quick and name in {"L", "XL", "D-3stop"}:
            continue
        ds = generate(SyntheticConfig(n_airports=na, n_hubs=nh, days=days, flights_per_route_day=fpd, seed=11))
        g = TemporalGraph(ds.flights)
        codes = list(ds.airports)
        rnd = random.Random(5)
        c = Constraints(max_stops=ms)
        queries = []
        while len(queries) < n_queries:
            o, d = rnd.sample(codes, 2)
            q = LegQuery(o, d, 0, win * D, c)
            if leg_front(g, q):
                queries.append(q)
        acc: dict[str, dict[str, list[float]]] = {}

        def rec(alg, **kw):
            for k, v in kw.items():
                acc.setdefault(alg, {}).setdefault(k, []).append(v)

        for q in queries:
            stats = SearchStats()
            exact, t = timed(lambda: leg_front(g, q, stats))
            ev = np.array([it.vec for it in exact], dtype=float)
            ref = ev.max(axis=0) * 1.1 + 1
            ideal = ev.min(axis=0)
            hv_exact = hypervolume_mc(ev, ref, ideal) or 1e-9
            rec("label-setting", time_ms=t, size=len(exact), recall=1.0, hv_ratio=1.0,
                prune_ratio=stats.prune_ratio)
            exact_set = {it.vec for it in exact}

            def score(alg, front, t):
                fv = {it.vec for it in front}
                arr = np.array(list(fv), dtype=float).reshape(-1, 5)
                rec(alg, time_ms=t, size=len(fv), recall=len(fv & exact_set) / len(exact_set),
                    hv_ratio=hypervolume_mc(arr, ref, ideal) / hv_exact if len(arr) else 0.0)

            if name in BRUTE_FORCE_SCALES:
                try:
                    bf, t = timed(lambda: brute_force_front(g, q, max_paths=3_000_000))
                except RuntimeError:  # path explosion: record as a failure instead of hanging
                    rec("brute-force", time_ms=float("nan"), size=float("nan"), recall=float("nan"), hv_ratio=float("nan"))
                else:
                    assert {it.vec for it in bf} == exact_set, "label-setting disagrees with brute force!"
                    score("brute-force", bf, t)
            if name not in {"XL", "D-3stop"}:
                (eps, n), t = timed(lambda: epsilon_constraint_front(g, q, grid=3))
                score("eps-constraint(MILP,g=3)", eps, t)
            ws, t = timed(lambda: weighted_sum_front(g, q, n_weights=50))
            score("weighted-sum(50 w)", ws, t)

        for alg, m in acc.items():
            rows.append({"scale": name, "airports": na, "flights": len(ds.flights), "algorithm": alg,
                         "queries": len(m["time_ms"]),
                         **{k: round(st.mean(v), 4) for k, v in m.items()}})
            r = rows[-1]
            print(f"{name:>2} {r['flights']:>7} fl  {alg:<26} {r['time_ms']:>10.1f} ms  |front|={r['size']:>7.1f} "
                  f"recall={r['recall']:.2f} hv={r['hv_ratio']:.3f}")
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = ["scale", "airports", "flights", "algorithm", "queries", "time_ms", "size", "recall", "hv_ratio", "prune_ratio"]
    with open(out_dir / "benchmark.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, restval="")
        w.writeheader()
        w.writerows(rows)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--queries", type=int, default=5)
    a = ap.parse_args()
    run(a.quick, a.queries, Path(__file__).parent / "results")
