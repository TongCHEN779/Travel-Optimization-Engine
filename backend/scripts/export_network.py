"""Export the world model + golden fixtures for the in-browser TypeScript engine.

    python scripts/export_network.py

Writes frontend/public/data/world.json (real airports, carriers, weekly simulated templates) and
frontend/test/golden.json (queries + the Pareto vectors the Python engine computes on schedules
instantiated by world.instantiate). `npm run verify` requires the TS port to reproduce them exactly.
"""
from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

from tripopt.graph import TemporalGraph
from tripopt.models import Constraints, RoundTripQuery
from tripopt.roundtrip import optimize_round_trip
from tripopt.world import AIRLINES, EPOCH, build_world, day_index, instantiate

ROOT = Path(__file__).resolve().parents[2] / "frontend"
MAX_STOPS_HORIZON = 4  # extra days instantiated after the latest possible return day


def schedule_window(q: RoundTripQuery) -> tuple[int, int]:
    """Days of weekly templates that must be instantiated for a query (mirrored in the TS client)."""
    return q.depart_from_day - 1, q.depart_to_day + 3 + q.max_stay_days + MAX_STOPS_HORIZON


def main() -> None:
    w = build_world()
    data = {
        "epoch": EPOCH.isoformat(),
        "airlines": [{"name": n, "tier": t} for n, t in AIRLINES],
        "airports": [
            {"code": a.code, "name": a.name, "city": a.city, "country": a.country, "region": a.region,
             "lat": a.lat, "lon": a.lon, "offset": a.offset_min, "hub": a.hub}
            for a in w.airports.values()
        ],
        # [origin, dest, local_dep, duration, base_price_cents, airline_idx, risk_micro, days_mask]
        "templates": [[t.origin, t.dest, t.local_dep, t.duration, t.base_price, t.airline, t.risk, t.days_mask] for t in w.templates],
    }
    (ROOT / "public" / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "public" / "data" / "world.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))

    codes = list(w.airports)
    rnd = random.Random(42)
    cases = []
    while len(cases) < 16:
        o, d = rnd.sample(codes, 2)
        c = Constraints(
            max_stops=rnd.choice([1, 1, 2, 2, 3]), passengers=rnd.choice([1, 1, 2, 3]),
            min_connection=rnd.choice([45, 60, 90]), max_layover=rnd.choice([300, 480, 720]),
            max_price_cents=rnd.choice([None, None, 400000]), max_duration=rnd.choice([None, None, 40 * 60]),
        )
        f = day_index(date(2027, 3, 1)) + rnd.randint(0, 400)
        q = RoundTripQuery(o, d, f, f + rnd.randint(0, 2), rnd.randint(2, 4), rnd.randint(5, 9), c,
                           w.airports[o].offset_min, w.airports[d].offset_min)
        lo, hi = schedule_window(q)
        res = optimize_round_trip(TemporalGraph(instantiate(w, lo, hi)), q)
        cases.append({
            "query": {"origin": o, "dest": d, "from": q.depart_from_day, "to": q.depart_to_day,
                      "minStay": q.min_stay_days, "maxStay": q.max_stay_days,
                      "maxStops": c.max_stops, "pax": c.passengers, "mct": c.min_connection, "maxLayover": c.max_layover,
                      "maxPrice": c.max_price_cents, "maxDuration": c.max_duration},
            "front": sorted(list(it.vec) for it in res.front),
        })
    (ROOT / "test").mkdir(exist_ok=True)
    (ROOT / "test" / "golden.json").write_text(json.dumps(cases))
    ne = sum(1 for c in cases if c["front"])
    print(f"{len(w.airports)} airports, {len(w.templates)} templates, {len(cases)} golden cases "
          f"({ne} non-empty, max front {max(len(c['front']) for c in cases)})")


if __name__ == "__main__":
    main()
