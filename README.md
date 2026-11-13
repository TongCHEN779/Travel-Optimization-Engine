# Travel Optimization Engine

Multi-objective itinerary optimisation for round-trip flights. Instead of sorting by one score, the engine computes
the **exact Pareto front** over price, total duration, stops, layover wait and disruption risk on a time-expanded
flight graph, then lets the user trade objectives off with weights and hard constraints.

**Live demo:** deployed to GitHub Pages by `.github/workflows/pages.yml` (no server: the engine runs in the browser).

**Status: Phases 1-2 complete** (engine, synthetic data, API, tests, benchmarks, web UI). PostgreSQL and real
flight-API ingestion are the next phases (see Roadmap).

## Data: what is real, what is simulated
| Real | Simulated (clearly labelled in the UI) |
|---|---|
| 66 global airports: IATA code, name, city, country, coordinates, standard UTC offset | which routes exist, timetables |
| Calendar dates and weekdays; local-time display | fares (distance-based model + date demand) |
| Carrier names, assigned by home region | which carrier flies a route, disruption risk |

`backend/src/tripopt/world.py` builds weekly timetable templates; `instantiate` expands them for any real date, so
any date can be searched. Nothing is a real offer. To use real offers, replace `instantiate` with an API
ingestion step producing the same `Flight` records (see Roadmap). Simplifications: standard time only (no DST), a
single fare per flight (no fare classes), no baggage rules.

## Quick start
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api,dev]"
pytest -q                                        # 10 correctness tests, incl. exact == brute force
python benchmarks/run_benchmarks.py --quick      # algorithm comparison
uvicorn tripopt.api.main:app --reload            # http://localhost:8000/docs

# in a second terminal
cd frontend && npm install && npm run dev         # http://localhost:3000, engine runs in-browser; no backend needed
```

**Serverless demo.** `frontend/lib/engine.ts` is a TypeScript port of the Python engine, running in the browser on
the world model `frontend/public/data/world.json` (real airports + weekly simulated templates, expanded for your dates). `npm run verify` checks it reproduces the Python
Pareto fronts exactly on golden cases (`python backend/scripts/export_network.py` regenerates data and fixtures);
CI runs this before every deploy. Set `NEXT_PUBLIC_API_URL` to use the FastAPI backend instead.
To enable Pages: repo Settings → Pages → Source: GitHub Actions.

**Web UI** (`frontend/`, Next.js + TypeScript, dependency-free SVG charts): query form, trade-off scatter (choose any
two objectives), 5-objective parallel coordinates, live preference sliders and hard-limit sliders, expandable
itineraries with layovers. Weights and limits re-rank/filter client-side with no re-query: filtering the exact front by
upper bounds gives exactly the constrained front (docs/MODEL.md).
Example: `POST /api/v1/search` with
`{"origin":"JFK","destination":"SIN","depart_from_day":1155,"depart_to_day":1157,"min_stay_days":5,"max_stay_days":10,
"max_stops":2,"weights":{"price":3,"risk":1}}`
returns the Pareto-optimal round trips ranked by your weights, a knee ("best compromise") flag and search stats.
`GET /api/v1/airports` lists valid codes. Days are local calendar days counted from 2024-01-01 (`depart_from_day`).

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
