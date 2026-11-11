# Travel Optimization Engine

Multi-objective itinerary optimisation for round-trip flights. Instead of sorting by one score, the engine computes
the **exact Pareto front** over price, total duration, stops, layover wait and disruption risk on a time-expanded
flight graph, then lets the user trade objectives off with weights and hard constraints.

**Status: Phases 1-2 complete** (engine, synthetic data, API, tests, benchmarks, web UI). PostgreSQL and real
flight-API ingestion are the next phases (see Roadmap).

## Quick start
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api,dev]"
pytest -q                                        # 10 correctness tests, incl. exact == brute force
python benchmarks/run_benchmarks.py --quick      # algorithm comparison
uvicorn tripopt.api.main:app --reload            # http://localhost:8000/docs

# in a second terminal
cd frontend && npm install && npm run dev         # http://localhost:3000 (API URL: NEXT_PUBLIC_API_URL)
```

**Web UI** (`frontend/`, Next.js + TypeScript, dependency-free SVG charts): query form, trade-off scatter (choose any
two objectives), 5-objective parallel coordinates, live preference sliders and hard-limit sliders, expandable
itineraries with layovers. Weights and limits re-rank/filter client-side with no re-query: filtering the exact front by
upper bounds gives exactly the constrained front (docs/MODEL.md).
Example: `POST /api/v1/search` with
`{"origin":"AAA","destination":"ABA","depart_from_day":2,"depart_to_day":4,"min_stay_days":3,"max_stay_days":7,
"max_stops":2,"weights":{"price":3,"risk":1}}`
returns the Pareto-optimal round trips ranked by your weights, a knee ("best compromise") flag and search stats.
`GET /api/v1/airports` lists valid codes.

## Layout
```
backend/src/tripopt/   models, synthetic generator, temporal graph, label-setting, baselines, MILP, round-trip, API
backend/tests/         correctness suite     backend/benchmarks/  benchmark harness + results
docs/MODEL.md          math model            docs/ALGORITHMS.md   algorithms & proofs
docs/BENCHMARKS.md     results + caveats
```

## Headline results (see docs/BENCHMARKS.md)
* Exact label-setting equals brute force on every tested instance; 95k-flight network answered in ~46 ms.
* Weighted-sum and coarse ε-constraint recover only ~40-80 % of the true Pareto itineraries.
* Brute force is actually faster on small sparse instances (documented, with the explanation).

## Roadmap
1. ~~Engine + synthetic data + tests + benchmark~~ (done)
2. ~~Next.js UI~~ (done)
3. PostgreSQL schema + ingestion/normalisation pipeline; real flight API (e.g. Amadeus/Duffel); calibrate risk
4. Adversarial scaling benchmark; OR-Tools CP-SAT comparison; multi-city, train legs, hotels
