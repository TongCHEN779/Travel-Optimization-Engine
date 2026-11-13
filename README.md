# Travel Optimization Engine

Multi-objective flight itinerary search. Instead of ranking by a single score, it computes the **exact Pareto front**
of round trips over five objectives (price, total duration, stops, layover wait, disruption risk) and lets you trade
them off interactively with preference weights and hard limits.

> **Data notice.** Airports, cities, time zones, dates and carrier names are real. Routes, timetables, fares and
> risk are **simulated**. Nothing here is a bookable offer. See [Data](#data).

**Live demo:** GitHub Pages, no server needed. The optimizer runs in your browser
(setup: repo Settings → Pages → Source: *GitHub Actions*).

## Features
- **Exact optimizer**: multi-objective label-setting with dominance pruning on a temporal flight graph; verified
  against brute force.
- **Round trips with real calendars**: date ranges, stay length, passengers, max stops; time-zone-aware.
- **Airport search boxes**: type a city, country, airport name or IATA code (Chinese names work too, e.g. 东京) and pick
  from live suggestions, with keyboard navigation and a swap button.
- **Interactive UI**: trade-off scatter (any two objectives), parallel coordinates, live weight sliders and hard-limit
  sliders, expandable itineraries with local times and layovers, a "best compromise" pick.
- **Benchmarks** against brute force, ε-constraint MILP (HiGHS) and weighted-sum scalarisation.

## Quick start

**Web app only** (the engine runs in the browser, no backend needed):
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

**Backend, tests and benchmarks:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api,dev]"
pytest -q                                      # 11 tests, incl. exact front == brute force
python benchmarks/run_benchmarks.py --quick    # algorithm comparison
uvicorn tripopt.api.main:app --reload          # REST API, docs at http://localhost:8000/docs
```
To make the web app use the REST API instead of the in-browser engine, set `NEXT_PUBLIC_API_URL=http://localhost:8000`.

## Data
| Real | Simulated |
|---|---|
| 66 global airports: IATA code, name, city, country, coordinates, standard UTC offset | which routes exist, timetables |
| Calendar dates, weekdays, local-time display | fares (distance model + date-dependent demand) |
| Airline names, assigned by home region | which carrier flies a route, disruption risk |

[`world.py`](backend/src/tripopt/world.py) builds weekly timetable templates and expands them for any requested date.
To use real offers later, replace that step with an API ingestion that produces the same `Flight` records.

Simplifications: standard time only (no DST), one fare per flight (no fare classes), no baggage rules.

## How it works
1. **Temporal graph.** Flights are nodes; `f → g` exists if `f` lands where `g` departs and the layover is between the
   minimum connection time and the maximum layover. This is a DAG ordered by departure time.
2. **Label-setting.** Flights are processed in departure order. Each carries a set of Pareto-optimal cost vectors;
   dominated vectors are discarded, as are those exceeding a hard limit or the stop budget.
3. **Round trips.** Outbound and inbound fronts are computed per calendar day (the only coupling is stay length), then
   combined exactly.
4. **Exactness.** Any continuation adds the same cost to every label at a flight, so a dominated label can never be
   part of an optimal path. Proofs: [docs/ALGORITHMS.md](docs/ALGORITHMS.md), model: [docs/MODEL.md](docs/MODEL.md).

Weights and hard limits in the UI re-rank and filter the exact front client-side; filtering by upper bounds gives
exactly the constrained front, so no re-query is needed.

## Verification
- `pytest`: label-setting equals brute force on every tested instance; round-trip result equals pairwise enumeration;
  hard-bound and time-zone consistency; API smoke test.
- `npm run verify` (in `frontend/`): the TypeScript engine reproduces the Python engine's Pareto fronts exactly on
  golden cases, and the airport search ranking passes its test cases. CI runs it before every deploy. Regenerate data and fixtures with
  `python backend/scripts/export_network.py`.

## Results
Leg-level, synthetic data, 4 queries per scale; details and caveats in [docs/BENCHMARKS.md](docs/BENCHMARKS.md).
- Exact label-setting equals brute force everywhere; a 95k-flight network is answered in ~46 ms.
- Weighted-sum and coarse ε-constraint recover only ~40–80 % of the true Pareto itineraries.
- On small, sparse instances brute force is actually faster (explained in the benchmark doc).

## Repository layout
```
backend/src/tripopt/    engine: models, graph, labelsetting, baselines, milp, roundtrip, world, api/
backend/tests/          correctness tests
backend/benchmarks/     benchmark harness and results
backend/scripts/        export of world data and golden fixtures for the web app
frontend/               Next.js app; lib/engine.ts is the in-browser engine
docs/                   MODEL.md (math), ALGORITHMS.md, BENCHMARKS.md
.github/workflows/      GitHub Pages deployment
```

## Limitations
- No real flight data yet; risk model is illustrative and not calibrated.
- Benchmarks use an older, fictional-airport generator, not the global world model.
- Web version fixes minimum connection to 60 min and maximum layover to 8 h.
- A 5-objective front can be large; the UI lists the top 30 by your weights.

## Roadmap
1. ~~Engine, tests, benchmarks~~ ✅
2. ~~Web UI, serverless deployment, real geography~~ ✅
3. Real flight API ingestion, PostgreSQL storage, risk calibration from on-time data
4. Adversarial scaling benchmark, OR-Tools CP-SAT comparison
5. Multi-city trips, train legs, hotels
