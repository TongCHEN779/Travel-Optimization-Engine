"""Export the default synthetic network + golden test fixtures for the in-browser TypeScript engine.

    python scripts/export_network.py

Writes frontend/public/data/network.json (flights as compact arrays) and
frontend/test/golden.json (queries with the Pareto vectors computed by the Python engine).
The TS engine must reproduce the golden fronts exactly (frontend: `npm run verify`).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from tripopt.graph import TemporalGraph
from tripopt.models import Constraints, RoundTripQuery
from tripopt.roundtrip import optimize_round_trip
from tripopt.synthetic import AIRLINES, SyntheticConfig, generate

ROOT = Path(__file__).resolve().parents[2] / "frontend"


def main() -> None:
    cfg = SyntheticConfig()  # identical to the API default (seed 7)
    ds = generate(cfg)
    names = list(AIRLINES)
    net = {
        "config": {"airports": cfg.n_airports, "days": cfg.days, "seed": cfg.seed},
        "airlines": names,
        "airports": [{"code": a.code, "name": a.name, "x": a.x, "y": a.y, "hub": a.is_hub} for a in ds.airports.values()],
        # [id, origin, dest, dep, arr, price_cents, airline_idx, risk_micro, seats]
        "flights": [[f.id, f.origin, f.dest, f.dep, f.arr, f.price_cents, names.index(f.airline), f.risk_micro, f.seats]
                    for f in ds.flights],
    }
    (ROOT / "public" / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "public" / "data" / "network.json").write_text(json.dumps(net, separators=(",", ":")))

    g = TemporalGraph(ds.flights)
    codes = list(ds.airports)
    rnd = random.Random(42)
    cases = []
    while len(cases) < 14:
        o, d = rnd.sample(codes, 2)
        c = Constraints(
            max_stops=rnd.choice([0, 1, 2, 3]), passengers=rnd.choice([1, 1, 2, 3]),
            min_connection=rnd.choice([45, 60, 90]), max_layover=rnd.choice([300, 480, 720]),
            max_price_cents=rnd.choice([None, None, 250000]), max_duration=rnd.choice([None, None, 30 * 60]),
        )
        f = rnd.randint(0, 10)
        q = RoundTripQuery(o, d, f, f + rnd.randint(0, 3), rnd.randint(1, 3), rnd.randint(3, 8), c)
        res = optimize_round_trip(g, q)
        cases.append({
            "query": {"origin": o, "dest": d, "from": q.depart_from_day, "to": q.depart_to_day,
                      "minStay": q.min_stay_days, "maxStay": q.max_stay_days,
                      "maxStops": c.max_stops, "pax": c.passengers, "mct": c.min_connection, "maxLayover": c.max_layover,
                      "maxPrice": c.max_price_cents, "maxDuration": c.max_duration},
            "front": sorted(list(it.vec) for it in res.front),
        })
    (ROOT / "test").mkdir(exist_ok=True)
    (ROOT / "test" / "golden.json").write_text(json.dumps(cases))
    nonempty = sum(1 for c in cases if c["front"])
    print(f"{len(ds.flights)} flights, {len(cases)} golden cases ({nonempty} non-empty, "
          f"max front {max(len(c['front']) for c in cases)})")


if __name__ == "__main__":
    main()
