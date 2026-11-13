# Mathematical model

## 1. Temporal graph

A schedule is a set of flights `f = (o_f, d_f, t^dep_f, t^arr_f, p_f, r_f)` with `t^arr_f > t^dep_f`.
Nodes of the graph are the flights themselves. Arc `f -> g` exists iff

```
d_f = o_g        and        MCT <= t^dep_g - t^arr_f <= L_max
```

(minimum connection time, maximum layover). Because `t^dep_g > t^arr_f > t^dep_f`, the graph is a **DAG ordered by
departure time**. A leg itinerary from origin `O` to destination `D` is a path `f_1 ... f_k` with `o_{f_1}=O`,
`d_{f_k}=D`, `t^dep_{f_1}` in the departure window, and `k-1 <= S_max` connections.
Flights into `O` or out of `D` are removed (they can only produce dominated detours).

## 2. Objectives (all minimised, all additive along a path)

| # | Objective | Definition |
|---|-----------|------------|
| 1 | price | `n * sum p_f` (n passengers) |
| 2 | duration | `t^arr_{f_k} - t^dep_{f_1}` = flight time + layovers |
| 3 | stops | `k - 1` |
| 4 | wait | `sum` of layovers |
| 5 | risk | `-log P(success)` = `sum r_f + sum c(layover_i)` |

**Risk.** Each flight is disrupted w.p. `q_f`; a connection with slack `s = layover - MCT` is missed w.p.
`0.30 * exp(-s/45min)`. Taking `-log(1 - q)` of each independent failure makes risk *exactly additive*
(`risk = -log P(no failure)`), which is what permits path-based optimisation. This is an illustrative model, to be
calibrated against real on-time data in the real-data phase.

**Integer arithmetic.** Prices are cents, times are minutes, risk is `round(1e6 * (-log(1-q)))`. All vector sums are
exact, so dominance and brute-force equality tests use `==` with no tolerances.

## 3. Pareto optimality

`a` dominates `b` iff `a_k <= b_k` for all k and `a != b`. The goal is the full Pareto front
`P = { x feasible : no feasible y dominates x }`, optionally under hard upper bounds `obj_k <= B_k`.

**Lemma (bounds commute with the front).** Filtering the unconstrained front by upper bounds gives the constrained
front (a dominator of a feasible point is no worse in every objective, hence also feasible). This is tested
(`test_hard_bounds_equal_filtered_front`) and lets the UI apply hard constraints interactively.

## 4. Round trips and coupling

Outbound and inbound objective vectors add. The only coupling is the stay length in calendar days
`r - a in [stay_min, stay_max]` where `a` is the outbound arrival day and `r` the return departure day.
Exactness requires keeping, per coupling key, a full Pareto front:

* outbound fronts per arrival day `a`, inbound fronts per departure day `r`;
* for each `r`: pool outbound fronts with admissible `a`, filter, then Minkowski-sum with the inbound front of `r`;
* final Pareto filter.

*Proof sketch.* If outbound path `x` is dominated by `x'` with the same arrival day (or pooled admissible days),
then `x' + y` dominates `x + y` for every compatible inbound `y` and is itself compatible. Symmetric for inbound.

**Time zones.** All timestamps are minutes since 2024-01-01 00:00 UTC, so durations and layovers are true elapsed
time. Stay length is counted in *local* calendar days at the destination (outbound arrival day vs. return
departure day); departure windows are local days at each end. Offsets are fixed standard time (no DST).

Not modelled yet: daylight saving, baggage/fare rules, airport-specific MCT, seat inventory beyond a
per-flight count.
