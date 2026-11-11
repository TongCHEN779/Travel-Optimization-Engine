# Algorithms

All live in `backend/src/tripopt/`.

| Algorithm | File | Exact? | Output |
|-----------|------|--------|--------|
| **Label-setting + dominance pruning** | `labelsetting.py` | yes | full Pareto front |
| Brute-force DFS + Pareto filter | `baselines.py` | yes (oracle) | full Pareto front |
| ε-constraint via MILP (HiGHS) | `milp.py` | only as grid→∞ | subset of front |
| Weighted-sum DP (weight sweep) | `baselines.py` | yes per weight | supported (convex-hull) points only |

## Label-setting
Flights are processed in departure order. A label at flight `g` is `(vector, parent)`. Labels at `g` are built from
all labels at predecessor flights `f` (found by bisect on arrival time) plus the vector delta of flying `g`, then
reduced to a Pareto set.

*Why per-node dominance is exact:* the delta added by any continuation depends only on `g` and its arrival time, the
same for every label at `g`. So `a` dominating `b` at `g` implies `a + delta` dominates `b + delta`.
We deliberately do **not** compare labels across different flights at the same airport: with waiting counted as an
objective, an earlier arrival does not dominate a later one.

Pruning: (i) bounds are monotone, so labels over any hard bound or over `S_max` are dropped at creation;
(ii) a layered BFS restricts the DAG to flights reachable within `S_max` connections.
Dominance filter: lexicographic sort then one forward pass (every dominator precedes its victim).

## ε-constraint (MILP)
Unit-flow formulation on the connection DAG with binary start, arc and end variables (see `milp.py`). One solve:
`min price s.t. obj_k <= ε_k`, followed by a second lexicographic stage (`min` positive-weighted sum of other
objectives at the optimal price) so the returned point is guaranteed Pareto-optimal. The front is approximated by a
grid over ε for non-primary objectives: cost grows as `grid^(m-2)`.

## Weighted sum
DP with state `(flight, #stops)`. Optimal for a fixed weight vector, but can only reach points on the convex hull of
the front: *non-supported* Pareto points (often the best "compromise" itineraries) are unreachable for any weights.

## Verification strategy
`tests/test_engine.py`: label-setting == brute force (as sets of vectors) for 1 and 2 stops; round-trip result ==
oracle that enumerates every outbound × inbound pair under the stay constraint; MILP extremes == front extremes;
ε-front ⊆ exact front; weighted-sum ⊆ exact front; bound-commutation lemma; path validity (connection times, sums).
