import itertools

import pytest

from tripopt.baselines import brute_force_front, weighted_sum_best, weighted_sum_front
from tripopt.labelsetting import leg_front
from tripopt.milp import LegMILP, epsilon_constraint_front
from tripopt.models import Constraints, LegQuery, MINUTES_PER_DAY, RoundTripQuery
from tripopt.pareto import dominates, pareto_filter
from tripopt.roundtrip import optimize_round_trip

D = MINUTES_PER_DAY


def vecs(front):
    return {it.vec for it in front}


def pairs(ds, n=12):
    codes = list(ds.airports)
    return list(itertools.islice(itertools.permutations(codes, 2), 0, None, max(1, 132 // n)))[:n]


def test_pareto_filter_basic():
    pts = [(1, 5), (2, 4), (3, 3), (2, 5), (3, 3), (4, 4)]
    got = {p for p in pareto_filter(pts, key=lambda p: p)}
    assert got == {(1, 5), (2, 4), (3, 3)}
    assert dominates((1, 1), (1, 2)) and not dominates((1, 1), (1, 1))


@pytest.mark.parametrize("max_stops", [1, 2])
def test_label_setting_equals_brute_force(small, max_stops):
    ds, g = small
    c = Constraints(max_stops=max_stops)
    checked = 0
    for o, d in pairs(ds):
        q = LegQuery(o, d, 0, 2 * D, c)
        ls, bf = leg_front(g, q), brute_force_front(g, q)
        assert vecs(ls) == vecs(bf), (o, d)
        checked += bool(bf)
    assert checked > 0  # the test must exercise non-empty fronts


def test_front_is_nondominated_and_paths_consistent(small):
    ds, g = small
    q = LegQuery(*list(ds.airports)[2:4], 0, 2 * D)
    for it in leg_front(g, q):
        fl = [g.by_id[i] for i in it.flights]
        assert fl[0].origin == q.origin and fl[-1].dest == q.dest
        assert all(a.dest == b.origin and a.arr + 60 <= b.dep for a, b in zip(fl, fl[1:]))
        assert it.vec[0] == sum(f.price_cents for f in fl)
        assert it.vec[1] == fl[-1].arr - fl[0].dep
        assert it.vec[2] == len(fl) - 1


def test_hard_bounds_equal_filtered_front(small):
    """Filtering the full front by upper bounds == searching with the bounds."""
    ds, g = small
    for o, d in pairs(ds, 8):
        base = leg_front(g, LegQuery(o, d, 0, 2 * D))
        if len(base) < 3:
            continue
        cap = sorted(it.vec[1] for it in base)[len(base) // 2]
        capped = leg_front(g, LegQuery(o, d, 0, 2 * D, Constraints(max_duration=cap)))
        assert vecs(capped) == {it.vec for it in base if it.vec[1] <= cap}


def test_milp_matches_exact_extremes(small):
    ds, g = small
    for o, d in pairs(ds, 6):
        q = LegQuery(o, d, 0, 2 * D)
        front = leg_front(g, q)
        if not front:
            continue
        m = LegMILP(g, q)
        for k in range(5):
            assert m.solve(k).vec[k] == min(it.vec[k] for it in front)


def test_epsilon_front_is_subset_of_exact(small):
    ds, g = small
    for o, d in pairs(ds, 8):
        q = LegQuery(o, d, 0, 2 * D)
        exact = vecs(leg_front(g, q))
        approx, _ = epsilon_constraint_front(g, q, grid=3)
        assert vecs(approx) <= exact


def test_weighted_sum_supported_subset_and_misses(small):
    ds, g = small
    total_exact = total_found = 0
    for o, d in pairs(ds, 12):
        q = LegQuery(o, d, 0, 2 * D)
        exact = vecs(leg_front(g, q))
        found = vecs(weighted_sum_front(g, q, n_weights=30))
        assert found <= exact  # every weighted-sum optimum is Pareto-optimal
        total_exact += len(exact); total_found += len(found)
    assert total_found <= total_exact


def test_round_trip_equals_bruteforce_pairing(small):
    ds, g = small
    c = Constraints(max_stops=1)
    codes = list(ds.airports)
    checked = 0
    for o, d in pairs(ds, 10):
        q = RoundTripQuery(o, d, 0, 1, 1, 2, c)
        res = optimize_round_trip(g, q)
        # oracle: enumerate every outbound x inbound pair satisfying stay constraint
        # exact oracle needs non-aggregated paths: enumerate without Pareto filtering
        outs = _all_paths(g, LegQuery(o, d, 0, 2 * D - 1, c))
        ins = _all_paths(g, LegQuery(d, o, 0, 6 * D, c))
        combos = []
        for a in outs:
            arr_day = g.by_id[a.flights[-1]].arr_day
            for b in ins:
                dep_day = g.by_id[b.flights[0]].dep_day
                if 1 <= dep_day - arr_day <= 2:
                    combos.append(tuple(x + y for x, y in zip(a.vec, b.vec)))
        want = {p for p in pareto_filter(combos, key=lambda p: p)}
        assert vecs(res.front) == want, (o, d)
        checked += bool(want)
    assert checked > 0


def _all_paths(g, q):
    """Unfiltered path enumeration (monkey-patched Pareto filter)."""
    import tripopt.baselines as bl

    orig = bl.pareto_filter
    bl.pareto_filter = lambda items, key: list(items)
    try:
        return bl.brute_force_front(g, q)
    finally:
        bl.pareto_filter = orig


def test_api_search_smoke():
    from fastapi.testclient import TestClient

    from tripopt.api.main import _state, app

    ds, _ = _state()
    codes = list(ds.airports)
    cl = TestClient(app)
    r = cl.post("/api/v1/search", json={"origin": codes[5], "destination": codes[20], "depart_from_day": 2,
                                        "depart_to_day": 4, "min_stay_days": 3, "max_stay_days": 6})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pareto_size"] >= 1 and body["itineraries"][0]["outbound"]
    assert cl.post("/api/v1/search", json={"origin": "ZZZ", "destination": codes[1], "depart_from_day": 0,
                                           "depart_to_day": 1}).status_code == 422
