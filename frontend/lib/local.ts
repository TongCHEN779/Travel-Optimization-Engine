import { Graph, optimizeRoundTrip } from "./engine";
import { instantiate, scheduleWindow, type World } from "./world";
import type { Airport, Flight, Itinerary, SearchResponse } from "./api";

export const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

let cache: Promise<World> | null = null;
const loadWorld = () =>
  (cache ??= fetch(`${BASE}/data/world.json`).then((r) => {
    if (!r.ok) throw new Error(`world.json: ${r.status}`);
    return r.json() as Promise<World>;
  }));

export async function localAirports(): Promise<Airport[]> {
  return (await loadWorld()).airports;
}

/** Expand the weekly simulated timetable for the needed real dates, then run the exact engine. */
export async function localSearch(body: Record<string, unknown>): Promise<SearchResponse> {
  const w = await loadWorld();
  const b = body as Record<string, number | string>;
  const ap = new Map(w.airports.map((a) => [a.code, a]));
  const o = ap.get(b.origin as string), d = ap.get(b.destination as string);
  if (!o || !d) throw new Error("unknown airport");
  const from = b.depart_from_day as number, to = b.depart_to_day as number, maxStay = b.max_stay_days as number;
  const [lo, hi] = scheduleWindow(from, to, maxStay);
  const graph = new Graph(instantiate(w, lo, hi));

  const t0 = performance.now();
  const res = optimizeRoundTrip(graph, {
    origin: o.code, dest: d.code, from, to, minStay: b.min_stay_days as number, maxStay,
    offO: o.offset, offD: d.offset,
    c: { maxStops: b.max_stops as number, mct: 60, maxLayover: 480, pax: b.passengers as number },
  });
  const ms = performance.now() - t0;

  const fj = (id: number): Flight => {
    const f = graph.byId.get(id)!;
    const a = ap.get(f.o)!, z = ap.get(f.d)!;
    return {
      id, from: f.o, to: f.d, dep_min: f.dep, arr_min: f.arr, price: f.price / 100, airline: w.airlines[f.airline].name,
      from_city: a.city, to_city: z.city, off_from: a.offset, off_to: z.offset,
    };
  };
  const itineraries: Itinerary[] = res.front.map((p) => ({
    is_knee: false, score: 0,
    objectives: { price: p.vec[0] / 100, duration_min: p.vec[1], stops: p.vec[2], wait_min: p.vec[3], risk: p.vec[4] / 1e6 },
    outbound: p.flights.slice(0, p.split).map(fj), inbound: p.flights.slice(p.split).map(fj),
  }));
  return {
    pareto_size: itineraries.length, returned: itineraries.length, itineraries,
    stats: {
      runtime_ms: ms, labels_generated: res.stats.generated, labels_kept: res.stats.kept,
      prune_ratio: res.stats.generated ? 1 - res.stats.kept / res.stats.generated : 0, round_trip_combinations: res.combinations,
    },
  };
}
