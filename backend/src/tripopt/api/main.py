"""FastAPI service. Phase 1 serves the seeded synthetic network from memory."""
from __future__ import annotations

import os
import time
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..graph import TemporalGraph
from ..models import OBJECTIVES, Constraints, RoundTripQuery
from ..roundtrip import optimize_round_trip
from ..selection import knee_index, weighted_scores
from ..world import EPOCH, build_world, instantiate

app = FastAPI(title="Travel Optimization Engine", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"], allow_headers=["*"],
)


@lru_cache(maxsize=1)
def _world():
    return build_world()


class SearchRequest(BaseModel):
    origin: str
    destination: str
    depart_from_day: int = Field(ge=0, description=f"local calendar day, as days since {EPOCH}")
    depart_to_day: int = Field(ge=0)
    min_stay_days: int = Field(default=3, ge=1)
    max_stay_days: int = Field(default=10, ge=1)
    passengers: int = Field(default=1, ge=1, le=9)
    max_stops: int = Field(default=2, ge=0, le=3)
    min_connection_minutes: int = Field(default=60, ge=20)
    max_layover_minutes: int = Field(default=480, ge=30)
    max_price: float | None = Field(default=None, description="total, currency units")
    max_duration_hours: float | None = None
    max_risk: float | None = Field(default=None, description="max total -log(survival) risk")
    weights: dict[str, float] | None = Field(default=None, description="keys: " + ",".join(OBJECTIVES))
    limit: int = Field(default=50, ge=1, le=500)


def _flight_json(f, w):
    a, z = w.airports[f.origin], w.airports[f.dest]
    return {"id": f.id, "from": f.origin, "to": f.dest, "dep_min": f.dep, "arr_min": f.arr,
            "price": f.price_cents / 100, "airline": f.airline, "from_city": a.city, "to_city": z.city,
            "off_from": a.offset_min, "off_to": z.offset_min}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/airports")
def airports():
    w = _world()
    return [{"code": a.code, "name": a.name, "city": a.city, "country": a.country, "region": a.region,
             "lat": a.lat, "lon": a.lon, "offset": a.offset_min, "hub": a.hub} for a in w.airports.values()]


@app.post("/api/v1/search")
def search(req: SearchRequest):
    w = _world()
    for code in (req.origin, req.destination):
        if code not in w.airports:
            raise HTTPException(422, f"unknown airport {code}")
    if req.origin == req.destination:
        raise HTTPException(422, "origin and destination must differ")
    if req.max_stay_days < req.min_stay_days or req.depart_to_day < req.depart_from_day:
        raise HTTPException(422, "invalid date or stay range")
    c = Constraints(
        max_stops=req.max_stops, min_connection=req.min_connection_minutes, max_layover=req.max_layover_minutes,
        passengers=req.passengers,
        max_price_cents=None if req.max_price is None else int(req.max_price * 100),
        max_duration=None if req.max_duration_hours is None else int(req.max_duration_hours * 60),
        max_risk_micro=None if req.max_risk is None else int(req.max_risk * 1e6),
    )
    q = RoundTripQuery(req.origin, req.destination, req.depart_from_day, req.depart_to_day,
                       req.min_stay_days, req.max_stay_days, c,
                       w.airports[req.origin].offset_min, w.airports[req.destination].offset_min)
    g = TemporalGraph(instantiate(w, q.depart_from_day - 1, q.depart_to_day + 3 + q.max_stay_days + 4))
    t0 = time.perf_counter()
    res = optimize_round_trip(g, q)
    elapsed = time.perf_counter() - t0
    front = res.front
    out = []
    if front:
        wt = None
        if req.weights:
            bad = set(req.weights) - set(OBJECTIVES)
            if bad:
                raise HTTPException(422, f"unknown weight keys {sorted(bad)}")
            wt = tuple(req.weights.get(k, 0.0) for k in OBJECTIVES)
        scores = weighted_scores(front, wt)
        knee = knee_index(front)
        order = sorted(range(len(front)), key=lambda i: scores[i])[: req.limit]
        for i in order:
            it = front[i]
            out.append({
                "score": float(scores[i]), "is_knee": i == knee,
                "objectives": {"price": it.vec[0] / 100, "duration_min": it.vec[1], "stops": it.vec[2],
                               "wait_min": it.vec[3], "risk": it.vec[4] / 1e6},
                "outbound": [_flight_json(g.by_id[x], w) for x in it.flights[: it.split]],
                "inbound": [_flight_json(g.by_id[x], w) for x in it.flights[it.split :]],
            })
    return {
        "pareto_size": len(front), "returned": len(out), "itineraries": out,
        "stats": {"runtime_ms": round(elapsed * 1000, 2), "labels_generated": res.stats.generated,
                  "labels_kept": res.stats.kept, "prune_ratio": round(res.stats.prune_ratio, 4),
                  "round_trip_combinations": res.n_combinations},
    }
